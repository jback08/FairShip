README for the field sub-directory

Magnetic fields for the FairShip simulation use the Geant4 VMC ("geant4_vmc") interface.
The "field/ShipFieldMaker" class is used to create fields, setting them to be either
global and/or local fields to specific volumes in the geometry. The VMC uses cm for 
distances and kGauss (0.1 Tesla) for magnetic fields. Here, we use the same cm unit for 
lengths, but use Tesla for magnetic fields, which the ShipFieldMaker class converts to 
kGauss units when passed to the VMC.

The script "gconfig/g4Config.C" creates a ShipFieldMaker pointer, whose makeFields 
function takes a control file that specifies what magnetic fields are required for 
the simulation. This control file, and any field maps that it uses, must be located in 
this "field" sub-directory.

The structure of the control file, such as "field/BFieldSetup.txt", uses specific 
keywords to denote what each line represents:

0) Comment lines start with the # symbol
1) "FieldMap" for using field maps to represent the magnetic field
2) "CopyMap" for copying a previously defined field map to another location (saving memory)
3) "Uniform" for creating a uniform magnetic field (no co-ordinate limits)
4) "Composite" for combining two or more field types/sources
5) "Global" for setting which (single or composite) field is the global one
6) "Region" for setting a local field to a specific volume, including the global field
7) "Local" for only setting a local field to a specific volume, ignoring the global field


The syntax for each of the above options are:

1) FieldMap MapLabel MapFileName x0 y0 z0

where MapLabel is the descriptive name of the field, MapFileName is the name of
the file containing the field map data, and x0,y0,z0 are the offset co-ordinates 
in cm for centering the field map.

The magnetic field from a field map (field/ShipBFieldMap) is found using trilinear 
interpolation based on the binned map data, which is essentially a 3d histogram.

The structure of the field map data file is as follows. The first line should be:

a) CLimits xMin xMax dx yMin yMax dy zMin zMax dz

where xMin, xMax and dx are the minimum, maximum and bin-width values (in cm) along 
the x axis, respectively, with similar values for the y and z axes.

The second line should contain the line

b) Bx(T) By(T) Bz(T)

which is just a label so that the user knows the following lines contain the 
field components.

c) The rest of the lines should contain the Bx, By and Bz components of the field
(in Tesla) for each "bin" in the order of increasing z, increasing y, then 
increasing x co-ordinates. 

The first data line corresponds to the point (xMin, yMin, zMin). The next set of 
lines correspond to the points (xMin, yMin, dz*zBin + zMin). 
After we reach z = zMax, y is incremented from yMin to yMin + dy, z is reset to zMin, 
and the rest of the lines follow by incrementing z up to zMax as before. 
When y = yMax has been reached, x is incremented by dx, while the y and z values are 
reset to yMin and zMin, and are both incremented using the same logic as before. 
This is repeated until the very last line of the data, which will correspond to 
the point (xMax, yMax, zMax).


2) CopyMap MapLabel MapToCopy x0 y0 z0

where MapToCopy is the name of the (previously defined) map to be copied, with the 
new co-ordinate offset specified by the values x0,y0,z0 (cm). Note that this will
reuse the field map data already stored in memory.

3) Uniform Label Bx By Bz

where Bx, By and Bz are the components of the uniform field (in Tesla),
valid for any x,y,z co-ordinate value.

4) Composite CompLabel Label1 ... LabelN

where CompLabel is the label of the composite field, comprising of the fields
named Label1 up to LabelN.

5) Global Label1 .. LabelN

where Label1 to LabelN are the labels of the field(s) that are combined
to represent the global one for the whole geometry.

6) Region VolName FieldLabel

where VolName is the name of the TGeo volume and FieldLabel is the
name of the local field that should be assigned to this volume. Note that this
will include the global field if it has been defined earlier in the 
configuration file.

7) Local VolName FieldLabel

where VolName is again the name of the TGeo volume and FieldLabel
is the name of the local field that should be assigned to this volume. This
will not include the global field, i.e. any particle inside this volume will
only see the local one.


Magnetic fields for local volumes are pre-enabled for the VMC with the setting 
"/mcDet/setIsLocalMagField true" in the "gconfig/g4config.in" file. Extra options 
for B field tracking (stepper/chord finders..), such as those mentioned here

https://root.cern.ch/drupal/content/magnetic-field

should be added to the (end of) the g4config.in file.
