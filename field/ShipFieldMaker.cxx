/*! \class ShipFieldMaker
  \brief Creates various magnetic fields and assigns them to geometry regions.

  The internal units here are cm for distances and Tesla for fields.
  Geant4 units for distance are mm, B fields = 0.001 megaVolt*ns/mm^2 (1 Tesla).
  VMC units require cm and kGauss (0.1 Tesla).
  Internally, use cm and Tesla, so keep distances unchanged but multiply B fields
  by 10 (1 Tesla = 10 kGauss)

  \author John Back <J.J.Back@warwick.ac.uk>
*/

#include "ShipFieldMaker.h"
#include "ShipBFieldMap.h"

#include "TGeoManager.h"
#include "TGeoUniformMagField.h"
#include "TGeoVolume.h"
#include "TVirtualMC.h"

#include <fstream>
#include <iostream>
#include <cstdlib>

ShipFieldMaker::ShipFieldMaker() :
    globalField_(0),
    theFields_(),
    T_(10.0)
{
}

ShipFieldMaker::~ShipFieldMaker()
{

    // Delete the various magnetic fields
    SFMap::iterator iter;
    for (iter = theFields_.begin(); iter != theFields_.end(); ++iter) {

	delete iter->second;

    }

    theFields_.clear();

    // The global field will be deleted by ROOT?
    // if (globalField_) {delete globalField_;}

}

void ShipFieldMaker::makeFields(const std::string& inputFile)
{

    std::cout<<"ShipFieldMaker::makeFields inputFile = "<<inputFile<<std::endl;

    std::ifstream getData(inputFile.c_str());
    std::string whiteSpace(" ");

    // Loop while the input file is readable
    while (getData.good()) {
	
	if (getData.peek() == '\n') {
	    
	    // Finish reading line
	    char c;
	    getData.get(c);
	    
	    // Stop while loop if we have reached the end of the file
	    if (getData.eof()) {break;}

	} else if (getData.peek() == '#') {
	    
	    // Skip comment line
	    getData.ignore(1000, '\n');
	    getData.putback('\n');

	    // Stop while loop if we have reached the end of the file
	    if (getData.eof()) {break;}

	} else {

	    // Read data line
	    std::string line("");
	    std::getline(getData, line);

	    // Stop while loop if we have reached the end of the file
	    if (getData.eof()) {break;}
	    
	    // Split up the line according to white spaces
	    std::vector<std::string> lineVect = this->splitString(line, whiteSpace);

	    size_t nWords = lineVect.size();

	    // Check to see if we have at least one keyword at the start of the line
	    if (nWords > 1) {

		TString keyWord(lineVect[0].c_str());
		keyWord.ToLower();

		if (keyWord.Contains("uniform")) {

		    // Create the uniform magnetic field
		    this->createUniform(lineVect);

		} else if (keyWord.Contains("fieldmap")) {

		    // Create the field map
		    this->createFieldMap(lineVect);

		} else if (keyWord.Contains("copymap")) {

		    // Copy (& translate) the field map
		    this->copyFieldMap(lineVect);

		} else if (keyWord.Contains("composite")) {

		    // Create the composite field
		    this->createComposite(lineVect);

		} else if (keyWord.Contains("global")) {

		    // Set which fields are global
		    this->setGlobalField(lineVect);

		} else if (keyWord.Contains("region")) {

		    // Set the local and global fields for the given volume
		    this->setRegionField(lineVect);

		} else if (keyWord.Contains("local")) {

		    // Set the field for the given volume as the local one only
		    this->setLocalField(lineVect);

		}

	    }

	}

    }

    getData.close();

}

void ShipFieldMaker::createUniform(const stringVect& inputLine)
{

    size_t nWords = inputLine.size();

    // Expecting a line such as:
    // Uniform LabelName Bx By Bz

    if (nWords == 5) {

	TString label(inputLine[1].c_str());

	// Check if the field is already in the map
	if (!this->gotField(label)) {

	    Double_t Bx = std::atof(inputLine[2].c_str())*T_;
	    Double_t By = std::atof(inputLine[3].c_str())*T_;
	    Double_t Bz = std::atof(inputLine[4].c_str())*T_;
	    
	    std::cout<<"Creating uniform field for "<<label.Data()<<std::endl;

	    TGeoUniformMagField* uField = new TGeoUniformMagField(Bx, By, Bz);
	    theFields_[label] = uField;

	} else {
	    std::cout<<"We already have a field with the name "
		     <<label.Data()<<std::endl;
	}

    } else {

	std::cout<<"Expecting 5 words for the definition of the uniform field: "
		 <<"Uniform Label Bx By Bz"<<std::endl;

    }


}

void ShipFieldMaker::createFieldMap(const stringVect& inputLine)
{

    size_t nWords = inputLine.size();

    // Expecting the line:
    // FieldMap LabelName mapFileName x0 y0 z0

    if (nWords == 6) {

	TString label(inputLine[1].c_str());

	// Check if the field is already in the map
	if (!this->gotField(label)) {

	    std::string mapFileName = inputLine[2];
	    Double_t x0 = std::atof(inputLine[3].c_str());
	    Double_t y0 = std::atof(inputLine[4].c_str());
	    Double_t z0 = std::atof(inputLine[5].c_str());
	    
	    std::cout<<"Creating map field for "<<label.Data()<<std::endl;
	    
	    ShipBFieldMap* mapField = new ShipBFieldMap(label.Data(), mapFileName,
							x0, y0, z0, T_);
	    theFields_[label] = mapField;

	} else {

	    std::cout<<"We already have a field with the name "
		     <<label.Data()<<std::endl;

	}

    } else {

	std::cout<<"Expecting 6 words for the definition of the field map: "
		 <<"FieldMap Label mapFileName x0 y0 z0"<<std::endl;

    }


}

void ShipFieldMaker::copyFieldMap(const stringVect& inputLine)
{

    size_t nWords = inputLine.size();

    // Expecting the line:
    // CopyMap LabelName MapLabelToCopy x0 y0 z0

    if (nWords == 6) {

	TString label(inputLine[1].c_str());

	// Check if the field is already in the map
	if (!this->gotField(label)) {
	    
	    // We want to try to copy and transpose an already existing field map
	    TString mapToCopy(inputLine[2].c_str());
	    Double_t x0 = std::atof(inputLine[3].c_str());
	    Double_t y0 = std::atof(inputLine[4].c_str());
	    Double_t z0 = std::atof(inputLine[5].c_str());

	    ShipBFieldMap* fieldToCopy = 
		dynamic_cast<ShipBFieldMap*>(this->getField(mapToCopy));

	    if (mapToCopy) {
		
		std::cout<<"Creating map field copy for "<<label.Data()<<std::endl;
		ShipBFieldMap* copiedMap = new ShipBFieldMap(label.Data(), *fieldToCopy,
							     x0, y0, z0);
		theFields_[label] = copiedMap;		    
		
	    }
	    

	} else {
	    std::cout<<"We already have a field with the name "
		     <<label.Data()<<std::endl;
	}

    } else {

	std::cout<<"Expecting 6 words for the copy of a field map: "
		 <<"CopyMap Label MapLabelToCopy x0 y0 z0"<<std::endl;

    }

}

void ShipFieldMaker::createComposite(const stringVect& inputLine)
{

    size_t nWords = inputLine.size();

    // Expecting a line such as:
    // Composite Label Field1 Field2 ... FieldN

    if (nWords > 2) {

	TString label(inputLine[1].c_str());

	// Check if the field is already in the map
	if (!this->gotField(label)) {

	    std::cout<<"Creating composite for "<<label.Data()<<std::endl;

	    // Loop over the list of fields and add them to the composite
	    std::vector<TVirtualMagField*> vectFields;
	    for (size_t i = 2; i < nWords; i++) {

		TString aLabel(inputLine[i].c_str());
		TVirtualMagField* aField = this->getField(aLabel);
		if (aField) {
		    std::cout<<"Adding field "<<aLabel<<std::endl;
		    vectFields.push_back(aField);
		}

	    }

	    ShipCompField* composite = new ShipCompField(label.Data(), vectFields);
	    theFields_[label] = composite;

	} else {
	    std::cout<<"We already have a field with the name "
		     <<label.Data()<<std::endl;
	}

    } else {

	std::cout<<"Expecting at least 3 words for the composite definition: "
		 <<"Composite Label Field1 Field2 ... FieldN"<<std::endl;

    }


}

void ShipFieldMaker::setGlobalField(const stringVect& inputLine)
{

    size_t nWords = inputLine.size();

    // Expecting the line:
    // Global Field1 ... FieldN

    if (globalField_) {delete globalField_;}

    if (nWords > 1) {

	std::cout<<"Setting the global field"<<std::endl;

	TString label("Global");

	std::vector<TVirtualMagField*> vectFields;
	for (size_t i = 1; i < nWords; i++) {

	    TString aLabel(inputLine[i].c_str());
	    TVirtualMagField* aField = this->getField(aLabel);
	    if (aField) {
		std::cout<<"Adding field "<<aLabel<<" to global"<<std::endl;
		vectFields.push_back(aField);
	    }

	}

	globalField_ = new ShipCompField(label.Data(), vectFields);
	// Set this as the global field in the virtual MC
	if (gMC) {gMC->SetMagField(globalField_);}

    } else {

	std::cout<<"Expecting at least two words for the global field definition: "
		 <<"Global Field1 ... FieldN"<<std::endl;

    }

}

void ShipFieldMaker::setRegionField(const stringVect& inputLine)
{

    // Set the local + global field for the region using info from inputLine

    size_t nWords = inputLine.size();

    // Expecting the line:
    // Region VolName FieldName

    if (nWords == 3) {
	
	TString volName(inputLine[1].c_str());
	TString fieldName(inputLine[2].c_str());

	std::cout<<"ShipFieldMaker::setRegionField for volume "
		 <<volName.Data()<<" and field "<<fieldName.Data()<<std::endl;

	TGeoVolume* theVol(0);
	if (gGeoManager) {theVol = gGeoManager->FindVolumeFast(volName.Data());}

	if (theVol) {	    

	    TVirtualMagField* localField = this->getField(fieldName);

	    if (localField) {

		// See if we have already combined this local field with the global field
		if (globalField_ && fieldName.Length() > 0) {

		    TString lgName(fieldName); lgName += "Global";
		    TVirtualMagField* lgField = this->getField(lgName);

		    if (!lgField) {

			// Create the combined local + global field and store in the internal map.
			// Other volumes that use the same combined field will use the stored pointer
			std::cout<<"Creating the combined field "<<lgName.Data()<<", with local field "
				 <<fieldName.Data()<<" with the global field for volume"<<volName.Data()<<std::endl;

			ShipCompField* combField = new ShipCompField(lgName.Data(), localField, globalField_);
			theFields_[lgName] = combField;
			theVol->SetField(combField);

		    } else {

			std::cout<<"Setting the field "<<lgName.Data()
				 <<" for volume "<<volName.Data()<<std::endl;
			theVol->SetField(lgField);

		    }

		} else {

		    std::cout<<"There is no global field defined. Just setting the local field"<<std::endl;
		    theVol->SetField(localField);

		}

	    } else {

		std::cout<<"Could not find the local field "<<fieldName.Data()<<std::endl;

	    }


	} else {

	    std::cout<<"Could not find the volume "<<volName<<std::endl;

	}

    } else {

	std::cout<<"Expecting 3 words for the region (local + global) field definition: "
		 <<"Region VolName LocalFieldToInclude"<<std::endl;

    }

}

void ShipFieldMaker::setLocalField(const stringVect& inputLine)
{

    // Set the local + global field for the region using info from inputLine

    size_t nWords = inputLine.size();

    // Expecting the line:
    // Region VolName FieldName

    if (nWords == 3) {
	
	TString volName(inputLine[1].c_str());
	TString fieldName(inputLine[2].c_str());

	std::cout<<"ShipFieldMaker::setLocalField for volume "
		 <<volName.Data()<<" and field "<<fieldName.Data()<<std::endl;

	TGeoVolume* theVol(0);
	if (gGeoManager) {theVol = gGeoManager->FindVolumeFast(volName.Data());}

	if (theVol) {	    

	    TVirtualMagField* localField = this->getField(fieldName);

	    if (localField) {

		theVol->SetField(localField);

	    } else {

		std::cout<<"Could not find the field "<<fieldName.Data()<<std::endl;
	    }

	} else {

	    std::cout<<"Could not find the volume "<<volName.Data()<<std::endl;
	}

    } else {

	std::cout<<"Expecting 3 words for the local field definition: "
		 <<"Local VolName LocalFieldName"<<std::endl;

    }

}


TVirtualMagField* ShipFieldMaker::getVolumeField(const TString& volName) const
{

    TVirtualMagField* theField(0);

    std::cout<<"Finding field for "<<volName<<std::endl;

    TGeoVolume* theVol(0);
    if (gGeoManager) {theVol = gGeoManager->FindVolumeFast(volName.Data());}

    if (theVol) {	    
	theField = dynamic_cast<TVirtualMagField*>(theVol->GetField());
    }

    return theField;

}

Bool_t ShipFieldMaker::gotField(const TString& label) const
{

    Bool_t result(kFALSE);

    // Iterate over the internal map and see if we have a match 
    SFMap::const_iterator iter;
    for (iter = theFields_.begin(); iter != theFields_.end(); ++iter) {
   
	TString key = iter->first;
	TVirtualMagField* theField = iter->second;

	// Check that we have the key already stored and the pointer is not null
	if (!key.CompareTo(label, TString::kExact) && theField) {
	    result = kTRUE;
	    break;
	}

    }

    return result;

}

TVirtualMagField* ShipFieldMaker::getField(const TString& label) const
{
  
    TVirtualMagField* theField(0);

    // Iterate over the internal map and see if we have a match 
    SFMap::const_iterator iter;
    for (iter = theFields_.begin(); iter != theFields_.end(); ++iter) {
   
	TString key = iter->first;
	TVirtualMagField* BField = iter->second;

	// Check that we have the key already stored
	if (!key.CompareTo(label, TString::kExact)) {
	    theField = BField;
	    break;
	}

    }

    return theField;

}

ShipFieldMaker::stringVect ShipFieldMaker::splitString(std::string& theString, 
						       std::string& splitter) const {

    // Code from STLplus
    stringVect result;

    if (!theString.empty() && !splitter.empty()) {

	for (std::string::size_type offset = 0;;) {

	    std::string::size_type found = theString.find(splitter, offset);

	    if (found != std::string::npos) {
		std::string tmpString = theString.substr(offset, found-offset);
		if (tmpString.size() > 0) {result.push_back(tmpString);}
		offset = found + splitter.size();
	    } else {
		std::string tmpString = theString.substr(offset, theString.size()-offset);
		if (tmpString.size() > 0) {result.push_back(tmpString);}
		break;
	    }
	}
    }
    
    return result;

}
