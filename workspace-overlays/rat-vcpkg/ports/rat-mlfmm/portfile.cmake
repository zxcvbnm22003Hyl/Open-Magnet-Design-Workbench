vcpkg_download_distfile(ARCHIVE
    URLS "https://gitlab.com/Project-Rat/rat-mlfmm/-/archive/v${VERSION}/rat-mlfmm-v${VERSION}.tar.gz"
    FILENAME "rat-mlfmm-v${VERSION}.tar.gz"
    SHA512 c832f9c06e2b15359a434b9f8d6a35f3a600d81d559b6c80f504e3b9b5c0ab610a7cb41357900640cda64d7bd78439cb8a7ef5b8cfacef2b04a419d19f88d4e1
)

vcpkg_extract_source_archive_ex(OUT_SOURCE_PATH SOURCE_PATH
    ARCHIVE "${ARCHIVE}"
    PATCHES
        fix-cuda13-deprecation.patch
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
        -DENABLE_CUDA=OFF
        -DENABLE_CUDA_DOUBLE_PRECISION=OFF
        -DENABLE_CUDA_FAST_MATH=OFF
        -DENABLE_TESTING=ON
        -DENABLE_EXAMPLES=OFF
        -DENABLE_MATLAB=OFF
    # OPTIONS_RELEASE -DOPTIMIZE=1
    # OPTIONS_DEBUG -DDEBUGGABLE=1
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(
    PACKAGE_NAME RatMLFMM          # Fix 1: because find_package(RatFMM)
    CONFIG_PATH lib/cmake/ratmlfmm # Fix 2:
)

# Fix 3: Remove include headers in debug directory
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")

# Fix 4: Remove debug/share directory, rest should already be in share
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
