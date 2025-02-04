
# targets
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR armv7a)
set(triple arm-linux-gnueabihf)

# compiler settings
set(CMAKE_C_COMPILER /usr/bin/arm-linux-gnueabihf-gcc CACHE INTERNAL "")
set(CMAKE_CXX_COMPILER /usr/bin/arm-linux-gnueabihf-g++ CACHE INTERNAL "")
set(CMAKE_C_COMPILER_TARGET ${triple})
set(CMAKE_CXX_COMPILER_TARGET ${triple})
set(CMAKE_C_COMPILER_EXTERNAL_TOOLCHAIN /usr/lib/llvm-15)
set(CMAKE_CXX_COMPILER_EXTERNAL_TOOLCHAIN /usr/lib/llvm-15)

# misc settings
set(CMAKE_SYSROOT /sysroot)
set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")