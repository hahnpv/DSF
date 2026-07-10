/**
 * @file xml.h
 * @brief XML parsing and navigation using Boost Property Tree.
 * 
 * Provides a wrapper around Boost Property Tree for XML configuration
 * parsing. The xmlnode class enables stateful navigation with parent
 * stack support for multi-level traversal.
 */
#pragma once

#include <boost/property_tree/ptree.hpp>
#include <boost/property_tree/xml_parser.hpp>
#include <string>
#include <vector>
#include <set>
#include <utility>
#include <sstream>
#include "../math/vec3.h"
#include "../math/mat3.h"
#include "../parse.h"

namespace dsf {
namespace xml {

using boost::property_tree::ptree;

/**
 * @brief Records which attributes/elements of a parsed document were actually
 *        consumed, and which lookups missed.
 *
 * Owned by the `xml` document and shared by every `xmlnode` derived from it.
 * After the configure pass, validate_config() (validate.h) diffs the document
 * against this record: attributes present in the deck but never read are
 * almost certainly typos — the classic "attrAsDouble silently returns 0"
 * failure — and lookups that missed show which values fell back to defaults.
 */
class ValidationContext {
public:
    /// A node consumed attribute/element `key` (keyed by node identity).
    void note_read(const void* node, const std::string& key) {
        read_.insert({node, key});
    }

    /// A lookup for `desc` found nothing (value defaulted).
    void note_miss(const std::string& desc) { missing_.insert(desc); }

    bool was_read(const void* node, const std::string& key) const {
        return read_.count({node, key}) > 0;
    }

    const std::set<std::string>& missing() const { return missing_; }

    void clear() { read_.clear(); missing_.clear(); }

private:
    std::set<std::pair<const void*, std::string>> read_;
    std::set<std::string> missing_;
};

/**
 * @brief Stateful XML node navigator.
 * 
 * Wraps Boost Property Tree to provide an intuitive API for XML navigation.
 * Maintains a parent stack for multi-level parent() traversal.
 * 
 * ## Usage
 * @code{.cpp}
 * xml doc("config.xml");
 * doc.parse();
 * xmlnode& root = *doc.xmlRoot;
 * for (auto child : root.children()) {
 *     std::string id = child.attrAsString("id");
 *     Vec3 pos = child.attrAsVec3("position");
 * }
 * @endcode
 */
class xmlnode {
public:
    /**
     * @brief Construct from ptree (root node).
     * @param tree Root property tree.
     * @param ctx  Optional usage recorder (see ValidationContext).
     */
    xmlnode(const ptree& tree, ValidationContext* ctx = nullptr)
        : tree_(&tree), current_(&tree), parent_stack_(), name_(""), ctx_(ctx) {}

    /**
     * @brief Internal constructor for navigation.
     */
    xmlnode(const ptree& tree, const ptree& current, std::vector<const ptree*> parent_stack,
            const std::string& name, ValidationContext* ctx = nullptr)
        : tree_(&tree), current_(&current), parent_stack_(parent_stack), name_(name), ctx_(ctx) {}

    /**
     * @brief Move to parent node.
     * @return Reference to this (modified).
     */
    xmlnode& parent() {
        if (!parent_stack_.empty()) {
            current_ = parent_stack_.back();
            parent_stack_.pop_back();
            name_ = ""; 
        }
        return *this;
    }

    /**
     * @brief Move to child by index.
     * @param i Child index (0-based, skips special nodes).
     * @return Reference to this (modified).
     */
    xmlnode& child(int i) {
        int count = 0;
        for (auto it = current_->begin(); it != current_->end(); ++it) {
            if (it->first == "<xmlattr>" || it->first == "<xmlcomment>" || it->first == "<xmltext>") {
                continue;
            }
            if (count == i) {
                parent_stack_.push_back(current_);
                current_ = &(it->second);
                name_ = it->first;
                return *this;
            }
            count++;
        }
        return *this;
    }

    /**
     * @brief Get number of children.
     * @return Child count (excludes special nodes).
     */
    unsigned int numchild() {
        unsigned int count = 0;
        for (auto it = current_->begin(); it != current_->end(); ++it) {
            if (it->first != "<xmlattr>" && it->first != "<xmlcomment>" && it->first != "<xmltext>") {
                count++;
            }
        }
        return count;
    }

    /**
     * @brief Check if attribute exists.
     * @param str Attribute name.
     * @return True if attribute exists.
     */
    bool findAttr(const std::string& str) {
        bool found = current_->get_optional<std::string>("<xmlattr>." + str).is_initialized();
        if (found) note_read(str);
        return found;
    }

    /**
     * @brief Get attribute as string.
     * @param str Attribute name (or child element name).
     * @return Attribute value, or empty string if not found.
     */
    std::string attrAsString(const std::string& str) {
        auto attr = current_->get_optional<std::string>("<xmlattr>." + str);
        if (attr) { note_read(str); return attr.get(); }
        auto child = current_->get_optional<std::string>(str);
        if (child) { note_read(str); return child.get(); }
        if (str == name_) { note_read(str); return current_->get_value<std::string>(); }
        note_miss(str);
        return "";
    }

    /**
     * @brief Get attribute as boolean.
     * @param str Attribute name.
     * @return True if value is "true" or "1".
     */
    bool attrAsBool(const std::string& str) {
        std::string value = attrAsString(str);
        return (value == "true" || value == "1");
    }

    /**
     * @brief Get attribute as Vec3.
     * @param str Attribute name (comma-separated x,y,z).
     * @return Vec3 value.
     */
    dsf::util::Vec3 attrAsVec3(const std::string& str) {
        std::string source = attrAsString(str);
        // Accept comma- and/or whitespace-separated components so a value like
        // "1 2 3" is not silently parsed as a single token and zeroed out.
        std::vector<double> v = dsf::util::split<double>(source, ", \t");
        if (v.size() >= 3) return dsf::util::Vec3(v[0], v[1], v[2]);
        if (!source.empty())
            std::cerr << "attrAsVec3: '" << str << "'=\"" << source
                      << "\" is not 3 numbers; using (0,0,0)" << std::endl;
        return dsf::util::Vec3(0, 0, 0);
    }

    /**
     * @brief Get attribute as Mat3.
     * @param str Attribute name (9 comma-separated values, row-major).
     * @return Mat3 value.
     */
    dsf::util::Mat3 attrAsMat3(const std::string& str) {
        std::string source = attrAsString(str);
        std::vector<double> m = dsf::util::split<double>(source, ", \t");
        if (m.size() >= 9) return dsf::util::Mat3(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
        if (!source.empty())
            std::cerr << "attrAsMat3: '" << str << "'=\"" << source
                      << "\" is not 9 numbers; using identity/zero" << std::endl;
        return dsf::util::Mat3();
    }

    /**
     * @brief Get attribute as double.
     * @param str Attribute name (or child element name).
     * @return Double value, or 0.0 if not found.
     */
    double attrAsDouble(const std::string& str) {
        auto attr = current_->get_optional<double>("<xmlattr>." + str);
        if (attr) { note_read(str); return attr.get(); }
        // Boost property_tree may reject integer strings ("0", "1") as doubles.
        // Fall back to std::stod on the raw string value.
        auto attr_str = current_->get_optional<std::string>("<xmlattr>." + str);
        if (attr_str) {
            note_read(str);
            try { return std::stod(attr_str.get()); } catch (...) {}
        }
        auto child = current_->get_optional<double>(str);
        if (child) { note_read(str); return child.get(); }
        auto child_str = current_->get_optional<std::string>(str);
        if (child_str) {
            note_read(str);
            try { return std::stod(child_str.get()); } catch (...) {}
        }
        if (str == name_) { note_read(str); return current_->get_value<double>(); }
        note_miss(str);
        return 0.0;
    }

    /**
     * @brief Check if child element exists.
     * @param str Child element name.
     * @return True if child exists.
     */
    bool findChild(const std::string& str) {
        bool found = current_->get_child_optional(str).is_initialized();
        if (found) note_read(str);
        return found;
    }

    /**
     * @brief Navigate to named child.
     * @param str Child element name.
     * @return Reference to this (modified to point to child).
     */
    xmlnode& search(const std::string& str) {
        auto child_opt = current_->get_child_optional(str);
        if (child_opt) {
            note_read(str);
            parent_stack_.push_back(current_);
            current_ = &child_opt.get();
            name_ = str;
        }
        return *this;
    }

    /**
     * @brief Get all children as vector.
     * @return Vector of child xmlnode objects.
     */
    std::vector<xmlnode> children() {
        std::vector<xmlnode> result;
        std::vector<const ptree*> new_stack = parent_stack_;
        new_stack.push_back(current_);
        for (const auto& child : *current_) {
            if (child.first != "<xmlattr>" && child.first != "<xmlcomment>" && child.first != "<xmltext>") {
                result.push_back(xmlnode(*tree_, child.second, new_stack, child.first, ctx_));
            }
        }
        return result;
    }

    /**
     * @brief Get current node name.
     * @return Node name string.
     */
    std::string name() { return name_; }

    /**
     * @brief Get the names of all attributes present on the current node.
     *
     * Introspection only (used by metadata/unknown-attribute checks): this
     * deliberately does NOT record reads in the ValidationContext, so calling
     * it cannot mask a real typo from the post-configure unused-attribute
     * validation (validate.h).
     */
    std::vector<std::string> attrNames() const {
        std::vector<std::string> names;
        if (auto attrs = current_->get_child_optional("<xmlattr>"))
            for (const auto& a : *attrs)
                names.push_back(a.first);
        return names;
    }

private:
    /// Record a successful attribute/element read for validation.
    void note_read(const std::string& key) {
        if (ctx_) ctx_->note_read(current_, key);
    }

    /// Record a lookup that found nothing (value defaulted to ""/0).
    void note_miss(const std::string& key) {
        if (!ctx_) return;
        auto id = current_->get_optional<std::string>("<xmlattr>.id");
        std::string where = "<" + (name_.empty() ? std::string("?") : name_)
                          + (id ? " id=\"" + id.get() + "\"" : "") + ">";
        ctx_->note_miss(where + " '" + key + "'");
    }

    const ptree* tree_;                     ///< Root tree reference.
    const ptree* current_;                  ///< Current node pointer.
    std::vector<const ptree*> parent_stack_;///< Parent navigation stack.
    std::string name_;                      ///< Current node name.
    ValidationContext* ctx_ = nullptr;      ///< Usage recorder (owned by xml doc).
};

/**
 * @brief XML document loader.
 * 
 * Loads and parses XML files, providing access to the root xmlnode.
 * 
 * ## Usage
 * @code{.cpp}
 * xml doc("simulation.xml");
 * doc.parse();
 * xmlnode& root = *doc.xmlRoot;
 * @endcode
 */
class xml {
public:
    /**
     * @brief Construct with filename.
     * @param filename Path to XML file.
     */
    xml(const std::string& filename) : filename_(filename) {
        xmlRoot = nullptr;
    }

    ~xml() { delete xmlRoot; }

    /**
     * @brief Parse the XML file.
     * 
     * Creates xmlRoot on success.
     */
    void parse() {
        try {
            boost::property_tree::read_xml(filename_, tree_);
            xmlRoot = new xmlnode(tree_, &validation_);
        } catch (const std::exception& e) {
            std::cerr << "Error parsing XML file " << filename_ << ": " << e.what() << std::endl;
        }
    }

    xmlnode* xmlRoot;   ///< Root node (valid after parse()).

    /// Underlying tree + usage record — consumed by validate_config().
    const ptree& tree() const { return tree_; }
    const ValidationContext& validation() const { return validation_; }

private:
    std::string filename_;      ///< Source filename.
    ptree tree_;                ///< Underlying Boost property tree.
    ValidationContext validation_;  ///< Attribute-usage record for validation.
};

} // namespace xml
} // namespace dsf
