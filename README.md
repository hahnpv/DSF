# DSF
Digital Simulation Framework

 
git clone https://github.com/hahnpv/DSF
cd DSF
mkdir BUILD
cd BUILD
cmake ../
make -j8


cd examples/static
./staticsixdof satellite.xml
./staticsixdof vehicle.xml


cd examples/dynamic
./staticsixdof satellite.xml
./staticsixdof vehicle.xml

to get vis to work under WSL:
https://github.com/microsoft/WSL/issues/2855


....
IWYU is active, to use: 

cd build
cmake -DCMAKE_CXX_INCLUDE_WHAT_YOU_USE="include-what-you-use" ..
make clean && make 2>&1 | grep "should remove"

....
to get everything on the path
export LD_LIBRARY_PATH="/home/philip/git/DSF/build:/home/philip/git/DSF/build/sixdof_build:$LD_LIBRARY_PATH"
