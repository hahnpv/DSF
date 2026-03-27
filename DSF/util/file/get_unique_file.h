/**
 * @file get_unique_file.h
 * @brief Log-rotation style filename manager.
 *
 * Implements true log rotation: the newest file is always the bare name,
 * and existing files are bumped to higher numbers before writing.
 *
 * Given "foo.h5", on successive calls:
 *   Run 1:  foo.h5
 *   Run 2:  foo.h5 (new), foo.0.h5 (was foo.h5)
 *   Run 3:  foo.h5 (new), foo.0.h5 (was foo.h5), foo.1.h5 (was foo.0.h5)
 */
#pragma once
#include <fstream>
#include <string>
#include <cstdio>    // std::rename

namespace dsf
{
	namespace util
	{
		class get_unique_file
		{
		public:
			/// Rotate existing files and return the bare filename for new output.
			get_unique_file(std::string candidate)
			{
				// Split at last dot: stem + ext
				auto dot = candidate.find_last_of('.');
				std::string stem = (dot != std::string::npos) ? candidate.substr(0, dot) : candidate;
				std::string ext  = (dot != std::string::npos) ? candidate.substr(dot)    : "";

				// If the bare file exists, rotate everything up
				if (file_exists(candidate)) {
					// Find the highest existing rotation number
					int max_n = -1;
					for (int i = 0; ; i++) {
						if (file_exists(stem + "." + std::to_string(i) + ext))
							max_n = i;
						else
							break;
					}

					// Rename in reverse order to avoid collisions:
					//   foo.1.h5 → foo.2.h5
					//   foo.0.h5 → foo.1.h5
					//   foo.h5   → foo.0.h5
					for (int i = max_n; i >= 0; i--) {
						std::string src = stem + "." + std::to_string(i) + ext;
						std::string dst = stem + "." + std::to_string(i + 1) + ext;
						std::rename(src.c_str(), dst.c_str());
					}
					// Rotate the bare file to .0
					std::string dst0 = stem + ".0" + ext;
					std::rename(candidate.c_str(), dst0.c_str());
				}

				// The bare filename is now available for the new run
				filename = candidate;
			}

			std::string filename;

		private:
			static bool file_exists(const std::string& path) {
				std::ifstream f(path);
				return f.good();
			}
		};
	}
}
