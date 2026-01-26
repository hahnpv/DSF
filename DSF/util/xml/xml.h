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

/// xmlnode provides a Boost Property Tree wrapper that mimics the original xmlnode API
/// Uses a stack of parent pointers to enable multi-level parent navigation
class xmlnode {
public:
    /// Constructor from ptree (root node, no parent)
    xmlnode(const ptree& tree) : tree_(&tree), current_(&tree), parent_stack_(), name_("") {}
    
    /// Internal constructor for navigation with parent stack
    xmlnode(const ptree& tree, const ptree& current, std::vector<const ptree*> parent_stack, const std::string& name) 
        : tree_(&tree), current_(&current), parent_stack_(parent_stack), name_(name) {}

    /// Move to parent node (stateful - modifies this xmlnode)
    xmlnode& parent() {
        if (!parent_stack_.empty()) {
            current_ = parent_stack_.back();
            parent_stack_.pop_back();
            // FIXME: We don't track parent names on stack, so name is lost on parent()
            // Using empty name is safe as standard attribute lookups still work
            name_ = ""; 
        }
        return *this;
    }

    /// Move to child by index (stateful - modifies this xmlnode, skips <xmlattr> node)
    xmlnode& child(int i) {
        int count = 0;
        for (auto it = current_->begin(); it != current_->end(); ++it) {
            // Skip the <xmlattr> node which Boost uses for attributes
            if (it->first == "<xmlattr>") {
                continue;
            }
            if (count == i) {
                parent_stack_.push_back(current_);  // Push current to parent stack
                current_ = &(it->second);
                name_ = it->first;
                return *this;
            }
            count++;
        }
        return *this;
    }

    /// Return number of children (excludes <xmlattr>)
    unsigned int numchild() {
        unsigned int count = 0;
        for (auto it = current_->begin(); it != current_->end(); ++it) {
            if (it->first != "<xmlattr>") {
                count++;
            }
        }
        return count;
    }

    /// Check if attribute exists
    bool findAttr(const std::string& str) {
        return current_->get_optional<std::string>("<xmlattr>." + str).is_initialized();
    }

    /// Get attribute as string (tries attribute first, then child element text)
    std::string attrAsString(const std::string& str) {
        // Try as attribute first
        auto attr = current_->get_optional<std::string>("<xmlattr>." + str);
        if (attr) {
            return attr.get();
        }
        // Fall back to child element text content
        auto child = current_->get_optional<std::string>(str);
        if (child) {
            return child.get();
        }
        // Fallback: if str matches current node name, return node value
        if (str == name_) {
             return current_->get_value<std::string>();
        }
        return "";
    }

    /// Get attribute as bool
    bool attrAsBool(const std::string& str) {
        std::string value = attrAsString(str);
        return (value == "true" || value == "1");
    }

    /// Get attribute as Vec3
    dsf::util::Vec3 attrAsVec3(const std::string& str) {
        std::string source = attrAsString(str);
        std::vector<double> v = dsf::util::split<double>(source, ",");
        if (v.size() >= 3) {
            return dsf::util::Vec3(v[0], v[1], v[2]);
        }
        return dsf::util::Vec3(0, 0, 0);
    }

    /// Get attribute as Mat3
    dsf::util::Mat3 attrAsMat3(const std::string& str) {
        std::string source = attrAsString(str);
        std::vector<double> m = dsf::util::split<double>(source, ",");
        if (m.size() >= 9) {
            return dsf::util::Mat3(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);
        }
        return dsf::util::Mat3();
    }

    /// Get attribute as double (tries attribute first, then child element text)
    double attrAsDouble(const std::string& str) {
        // Try as attribute first
        auto attr = current_->get_optional<double>("<xmlattr>." + str);
        if (attr) {
            return attr.get();
        }
        // Fall back to child element text content
        auto child = current_->get_optional<double>(str);
        if (child) {
            return child.get();
        }
        // Fallback: if str matches current node name, return node value
        if (str == name_) {
             return current_->get_value<double>();
        }
        return 0.0;
    }

    /// Check if child exists
    bool findChild(const std::string& str) {
        return current_->get_child_optional(str).is_initialized();
    }

    /// Search for child by name (returns *this modified to point to child, with parent stack updated)
    xmlnode& search(const std::string& str) {
        auto child_opt = current_->get_child_optional(str);
        if (child_opt) {
            // When searching for a child, add current to parent stack
            parent_stack_.push_back(current_);
            current_ = &child_opt.get();
            name_ = str;
            return *this;
        }
        // If not found, return *this (unchanged)
        return *this;
    }

    /// Get all children
    std::vector<xmlnode> children() {
        std::vector<xmlnode> result;
        std::vector<const ptree*> new_stack = parent_stack_;
        new_stack.push_back(current_);
        for (const auto& child : *current_) {
            if (child.first != "<xmlattr>") {
                // Pass child name
                result.push_back(xmlnode(*tree_, child.second, new_stack, child.first));
            }
        }
        return result;
    }

    /// Get node name
    std::string name() {
        return name_;
    }

private:
    const ptree* tree_;                     // Root tree
    const ptree* current_;                  // Current node
    std::vector<const ptree*> parent_stack_; // Stack of parent nodes for multi-level navigation
    std::string name_;                      // Current node name
};

/// Simple XML loader
class xml {
public:
    xml(const std::string& filename) : filename_(filename) {
        xmlRoot = nullptr;
    }

    ~xml() {
        delete xmlRoot;
    }

    void parse() {
        try {
            boost::property_tree::read_xml(filename_, tree_);
            xmlRoot = new xmlnode(tree_);
        } catch (const std::exception& e) {
            std::cerr << "Error parsing XML file " << filename_ << ": " << e.what() << std::endl;
        }
    }

    xmlnode* xmlRoot;

private:
    std::string filename_;
    ptree tree_;
};

} // namespace xml
} // namespace dsf
