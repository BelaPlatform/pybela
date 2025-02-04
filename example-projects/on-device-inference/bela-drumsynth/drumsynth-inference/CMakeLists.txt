cmake_minimum_required(VERSION 3.18)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT DEFINED PROJECT_NAME)
    set(PROJECT_NAME "project")
endif()

project(${PROJECT_NAME})

####################################

add_compile_options(
    -march=armv7-a
    -mtune=cortex-a8
    -mfloat-abi=hard
    -mfpu=neon
    -Wno-psabi
)

add_compile_options(
    -O3
    -g 
    -fPIC
    -ftree-vectorize
    -ffast-math
)

add_compile_definitions(DXENOMAI_SKIN_posix)

####################################

set(BELA_ROOT "${CMAKE_SYSROOT}/root/Bela") 
set(SYS_ROOT "${CMAKE_SYSROOT}")

find_library(COBALT_LIB REQUIRED
    NAMES cobalt libcobalt
    HINTS "${CMAKE_SYSROOT}/usr/xenomai/lib"
)

find_library(NEON_LIB REQUIRED
    NAMES NE10 libNE10
    HINTS "${CMAKE_SYSROOT}/usr/lib"
)

find_library(MATHNEON_LIB REQUIRED
    NAMES mathneon libmathneon
    HINTS "${CMAKE_SYSROOT}/usr/lib"
)

####################################

set(EXE_NAME ${PROJECT_NAME})

file(GLOB SRC_FILES *.cpp)
include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/../src)
file(GLOB_RECURSE SRC_FILES ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp ${CMAKE_CURRENT_SOURCE_DIR}/*.h ${CMAKE_CURRENT_SOURCE_DIR}/../src/*.cpp ${CMAKE_CURRENT_SOURCE_DIR}/../src/*.h)

# Check if main.cpp exists in the current directory
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/main.cpp")
    list(APPEND SRC_FILES "${CMAKE_CURRENT_SOURCE_DIR}/main.cpp")
else()
    list(APPEND SRC_FILES "/sysroot/root/Bela/core/default_main.cpp")
endif()

add_executable(${EXE_NAME} ${SRC_FILES})

target_include_directories(
    ${EXE_NAME} PRIVATE ${BELA_ROOT} ${BELA_ROOT}/include ${CMAKE_CURRENT_SOURCE_DIR}
)
list(APPEND CMAKE_PREFIX_PATH /opt/include/torch)
find_package(Torch REQUIRED)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")
target_link_libraries(
    ${EXE_NAME}
    PRIVATE
    ${BELA_ROOT}/lib/libbelafull.so
    ${COBALT_LIB}
    ${NEON_LIB}
    ${MATHNEON_LIB}
    ${TORCH_LIBRARIES}
    dl
    prussdrv
    asound
    atomic
    sndfile
    pthread
    rt
)