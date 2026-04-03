vcpkg_download_distfile(ARCHIVE
    URLS "https://gitlab.com/Project-Rat/rat-models/-/archive/v${VERSION}/rat-models-v${VERSION}.tar.gz"
    FILENAME "rat-models-v${VERSION}.tar.gz"
    SHA512 5e686a6d0fa9c856ee8d079d8e9a88f6c00ce876ce32225b9ce1417feb52db0d31b829697cb8c289469dafc7e88f55e0ecc4830e5871118c5fb3fe5a19beffd2
)

vcpkg_extract_source_archive_ex(OUT_SOURCE_PATH SOURCE_PATH
    ARCHIVE "${ARCHIVE}"
)

vcpkg_check_features(OUT_FEATURE_OPTIONS FEATURE_OPTIONS
  FEATURES
    nl   ENABLE_NL_SOLVER
#   INVERTED_FEATURES
#     tbb   ROCKSDB_IGNORE_PACKAGE_TBB
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    GENERATOR "Ninja"
    OPTIONS
        -DENABLE_TESTING=ON
        -DENABLE_EXAMPLES=OFF
        -DENABLE_PARAVIEW_VTK=OFF
        -DENABLE_MPI=OFF
        ${FEATURE_OPTIONS}
    # OPTIONS_RELEASE -DOPTIMIZE=1
    # OPTIONS_DEBUG -DDEBUGGABLE=1
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(
    PACKAGE_NAME RatModels          # Fix 1: because find_package(RatModels)
    CONFIG_PATH lib/cmake/ratmodels # Fix 2:
)

# Fix 3: Remove include headers in debug directory
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")

# Fix 4: Remove debug/share directory, rest should already be in share
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
