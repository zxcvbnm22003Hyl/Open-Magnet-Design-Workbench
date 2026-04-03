vcpkg_download_distfile(ARCHIVE
    URLS "https://gitlab.com/Project-Rat/rat-nl/-/archive/v${VERSION}/rat-nl-v${VERSION}.tar.gz"
    FILENAME "rat-nl-v${VERSION}.tar.gz"
    SHA512 bbfdfbfebf0873dcc420925c631e41d1bd9b3a22e27d3400a1c9fe1b25250877725ffc115d3369f4d215b5d77711125441a1fb8fee27357579ca2a69dec8d396
)

vcpkg_extract_source_archive_ex(OUT_SOURCE_PATH SOURCE_PATH
    ARCHIVE "${ARCHIVE}"
)

# # Check if one or more features are a part of a package installation.
# # See /docs/maintainers/vcpkg_check_features.md for more details
# vcpkg_check_features(OUT_FEATURE_OPTIONS FEATURE_OPTIONS
#   FEATURES
#     tbb   WITH_TBB
#   INVERTED_FEATURES
#     tbb   ROCKSDB_IGNORE_PACKAGE_TBB
# )

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    GENERATOR "Ninja"
    OPTIONS
        -DENABLE_TESTING=ON
        -DENABLE_EXAMPLES=OFF
        -DENABLE_CHOLMOD=ON
        -DENABLE_CHOLMOD_GPL=ON
        -DENABLE_UMFPACK=ON
        -DENABLE_PARU=OFF
        -DENABLE_QDLDL=OFF
        -DNVECTOR_PTHREADS=OFF # Windows is not POSIX so no PTHREADS
    # OPTIONS_RELEASE -DOPTIMIZE=1
    # OPTIONS_DEBUG -DDEBUGGABLE=1
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(
    PACKAGE_NAME RatNL          # Fix 1: because find_package(RatNL)
    CONFIG_PATH lib/cmake/ratnl # Fix 2:
)

# Fix 3: Remove include headers in debug directory
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")

# Fix 4: Remove debug/share directory, rest should already be in share
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
