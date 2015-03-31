// Configuration macro for Geant4 VirtualMC
void Config()
{
///    Create the run configuration
/// In constructor user has to specify the geometry input
/// and select geometry navigation via the following options:
/// - geomVMCtoGeant4   - geometry defined via VMC, G4 native navigation
/// - geomVMCtoRoot     - geometry defined via VMC, Root navigation
/// - geomRoot          - geometry defined via Root, Root navigation
/// - geomRootToGeant4  - geometry defined via Root, G4 native navigation
/// - geomGeant4        - geometry defined via Geant4, G4 native navigation
///
/// The second argument in the constructor selects physics list:
/// - emStandard         - standard em physics (default)
/// - emStandard+optical - standard em physics + optical physics
/// - XYZ                - selected hadron physics list ( XYZ = LHEP, QGSP, ...)
/// - XYZ+optical        - selected hadron physics list + optical physics
///
/// The third argument activates the special processes in the TG4SpecialPhysicsList,
/// which implement VMC features:
/// - stepLimiter       - step limiter (default) 
/// - specialCuts       - VMC cuts
/// - specialControls   - VMC controls for activation/inactivation selected processes
/// - stackPopper       - stackPopper process
/// When more than one options are selected, they should be separated with '+'
/// character: eg. stepLimit+specialCuts.

   cout<<"Started gconfig/g4Config.C"<<endl;

   TG4RunConfiguration* runConfiguration 
           = new TG4RunConfiguration("geomRoot", "QGSP_BERT_HP_PEN", "stepLimiter+specialCuts+specialControls");

/// Create the G4 VMC 
   TGeant4* geant4 = new TGeant4("TGeant4", "The Geant4 Monte Carlo", runConfiguration);
   cout << "Geant4 has been created." << endl;

/// create the Specific stack
   ShipStack *stack = new ShipStack(1000);
   stack->StoreSecondaries(kTRUE);
   stack->SetMinPoints(0);
   geant4->SetStack(stack);
   //if(FairRunSim::Instance()->IsExtDecayer()){
   //   // does not work ! TVirtualMCDecayer* decayer = TPythia8Decayer::Instance();
   //  TVirtualMCDecayer* decayer = TVirtualMCDecayer* TPythia8Decayer();
   //  geant4->SetExternalDecayer(decayer);
   //}
  
   /// Set the fields (global and/or local to the TGeo volumes)
   cout << "Creating the magnetic fields" << endl;
   ShipFieldMaker* fieldMaker = new ShipFieldMaker();
   fieldMaker->makeFields("field/BFieldSetup.txt");
   // Use this to recreate the uniform fields set-up
   //fieldMaker->makeFields("field/UniformBFieldSetup.txt");

   // Create z-x and y-z plots of the magnetic field
   Double_t xMin(-300.0), xMax(300.0), dx(1.0);
   Double_t yMin(-300.0), yMax(300.0), dy(1.0);
   Double_t zMin(-9000.0), zMax(5000.0), dz(1.0);
   //Double_t zMin(-9000.0), zMax(-3000.0), dz(1.0);
   TVector3 xAxis(xMin, xMax, dx);
   TVector3 yAxis(yMin, yMax, dy);
   TVector3 zAxis(zMin, zMax, dz);
   fieldMaker->plotZXField(zAxis, xAxis, "BField_zx.png");
   //fieldMaker->plotZYField(zAxis, yAxis, "BField_zy.png");

/// Customise Geant4 setting
/// (verbose level, global range cut, ..)

   TString configm(gSystem->Getenv("VMCWORKDIR"));
   configm1 = configm + "/gconfig/g4config.in";
   cout << " -I g4Config() using g4conf  macro: " << configm1 << endl;
   //set geant4 specific stuff
   geant4->SetMaxNStep(10000);  // default is 30000
   geant4->ProcessGeantMacro(configm1.Data());

   cout<<"Finished gconfig/g4Config.C"<<endl;

}
