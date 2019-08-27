#include <fx.h>

#include "vis/MainWindow.h"

#include <iostream>
using namespace std;
using namespace dsf::vis;
int main(int argc, char *argv[]) 
{
	FXApp application("Simulation");
	application.init(argc,argv);
	new MainWindow(&application, 0.0, 40.0, 0.01);
	application.create();
	return application.run();
}
