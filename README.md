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
