For the time being (lacking profit motive, lacking relevance to current employment) I am not advancing the development of DSF. It contains the utility I require for now.

Future development would address the following 

## Presentation quality plots and graphics using Python
1. Add arcgis maps to cartopy: https://stackoverflow.com/questions/37423997/cartopy-shaded-relief/38534299#38534299
    * can also do sun shading etc.
    * add animation with moving satellite 
    * can do zoomed in plots for reentry/launch/etc
2. https://pypi.org/project/vtk/ 
    * 3D animation with time trail
    * https://docs.enthought.com/mayavi/mayavi/mlab_animating.html (mayavi layers on vtk)
      * Mayavi example: https://stackoverflow.com/questions/53074908/map-an-image-onto-a-sphere-and-plot-3d-trajectories

## Refactor Vis / Net
1. Generate outputs for open source tools like Google Earth or XPLANE

2. Delete Net - I don't see a reason to distribute compute, easier to couple with a professional quality visualizer over some defined protocol than writing your own

## Fix/Replace XML
1. your XML reader is tab-dependent!!!!! (boost property tree does xml read/write) 
2. model names get truncated after a whitespace and/or cause sim to crash
    * parse.h splits by space along with other tokens, so its just by chance sometimes you split a space and get a valid(partial) name and other times a sim crash
    * C++14 built in answer: https://stackoverflow.com/questions/46535176/c-split-a-string-by-blank-spaces-unless-it-is-enclosed-in-quotes-and-store-in
3. You should probably use an alternate XML package
    * https://pugixml.org/docs/quickstart.html. Handles recursive out of the box.
    * Boost impl of recursion: https://stackoverflow.com/questions/30251529/need-help-recursively-creating-a-directory-tree-using-the-boost-property-tree-li

## Demonstrate parallel processing 
1. DSF branch to demo threading capability? barrier seems like an easy thread stopper to maintain sync, add mutexes to integrator/variable libraries
    * https://www.modernescpp.com/index.php/latches-and-barriers
