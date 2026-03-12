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
#include <sstream>
#include "../math/vec3.h"
#include "../math/mat3.h"
#include "../parse.h"

namespace dsf {
namespace xml {

using boost::property_tree::ptree;

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
     */
    xmlnode(const ptree& tree) : tree_(&tree), current_(&tree), parent_stack_(), name_("") {}
    
    /**
     * @brief Internal constructor for navigation.
     */
    xmlnode(const ptree& tree, const ptree& current, std::vector<const ptree*> parent_stack, const std::string& name) 
        : tree_(&tree), current_(&current), parent_stack_(parent_stack), name_(name) {}

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
        return current_->get_optional<std::string>("<xmlattr>." + str).is_initialized();
    }

    /**
     * @brief Get attribute as string.
     * @param str Attribute name (or child element name).
     * @return Attribute value, or empty string if not found.
     */
    std::string attrAsString(const std::string& str) {
        auto attr = current_->get_optional<std::string>("<xmlattr>." + str);
        if (attr) return attr.get();
        auto child = current_->get_optional<std::string>(str);
        if (child) return child.get();
        if (str == name_) return current_->get_value<std::string>();
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
        std::vector<double> v = dsf::util::split<double>(source, ",");
        if (v.size() >= 3) return dsf::util::Vec3(v[0], v[1], v[2]);
        return dsf::util::Vec3(0, 0, 0);
    }

    /**
     * @brief Get attribute as Mat3.
     * @param str Attribute name (9 comma-separated values, row-major).
     * @return Mat3 value.
     */
    dsf::util::Mat3 attrAsMat3(const std::string& str) {
        std::string source = attrAsString(str);
        std::vector<double> m = dsf::util::split<double>(source, ",");
        if (m.size() >= 9) return dsf::util::Mat3(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
        return dsf::util::Mat3();
    }

    /**
     * @brief Get attribute as double.
     * @param str Attribute name (or child element name).
     * @return Double value, or 0.0 if not found.
     */
    double attrAsDouble(const std::string& str) {
        auto attr = current_->get_optional<double>("<xmlattr>." + str);
        if (attr) return attr.get();
        // Boost property_tree may reject integer strings ("0", "1") as doubles.
        // Fall back to std::stod on the raw string value.
        auto attr_str = current_->get_optional<std::string>("<xmlattr>." + str);
        if (attr_str) {
            try { return std::stod(attr_str.get()); } catch (...) {}
        }
        auto child = current_->get_optional<double>(str);
        if (child) return child.get();
        auto child_str = current_->get_optional<std::string>(str);
        if (child_str) {
            try { return std::stod(child_str.get()); } catch (...) {}
        }
        if (str == name_) return current_->get_value<double>();
        return 0.0;
    }

    /**
     * @brief Check if child element exists.
     * @param str Child element name.
     * @return True if child exists.
     */
    bool findChild(const std::string& str) {
        return current_->get_child_optional(str).is_initialized();
    }

    /**
     * @brief Navigate to named child.
     * @param str Child element name.
     * @return Reference to this (modified to point to child).
     */
    xmlnode& search(const std::string& str) {
        auto child_opt = current_->get_child_optional(str);
        if (child_opt) {
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
                result.push_back(xmlnode(*tree_, child.second, new_stack, child.first));
            }
        }
        return result;
    }

    /**
     * @brief Get current node name.
     * @return Node name string.
     */
    std::string name() { return name_; }

private:
    const ptree* tree_;                     ///< Root tree reference.
    const ptree* current_;                  ///< Current node pointer.
    std::vector<const ptree*> parent_stack_;///< Parent navigation stack.
    std::string name_;                      ///< Current node name.
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
            xmlRoot = new xmlnode(tree_);
        } catch (const std::exception& e) {
            std::cerr << "Error parsing XML file " << filename_ << ": " << e.what() << std::endl;
        }
    }

    xmlnode* xmlRoot;   ///< Root node (valid after parse()).

private:
    std::string filename_;  ///< Source filename.
    ptree tree_;            ///< Underlying Boost property tree.
};

} // namespace xml
} // namespace dsf
