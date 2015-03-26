/*! \class ShipFieldMaker
  \brief Creates various magnetic fields and assigns them to geometry regions
  \author John Back <J.J.Back@warwick.ac.uk>
*/

#ifndef ShipFieldMaker_H
#define ShipFieldMaker_H

#include "ShipCompField.h"

#include "TString.h"
#include "TVirtualMagField.h"

#include <map>
#include <string>
#include <vector>

class ShipFieldMaker
{

 public:

    //! Constructor
    ShipFieldMaker();

    //! Destructor
    virtual ~ShipFieldMaker();

    //! Typedef for a TString-TVirtualMagField* map
    typedef std::map<TString, TVirtualMagField*> SFMap;

    //! Typedef of a vector of strings
    typedef std::vector<std::string> stringVect;

    //! Set-up all the fields and assign to local volumes
    /*!
      \param [in] inputFile The file containing the information about fields and volumes
    */
    void makeFields(const std::string& inputFile);

    //! Create the uniform field based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void createUniform(const stringVect& inputLine);

    //! Create the field map based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void createFieldMap(const stringVect& inputLine);

    //! Copy (&translate) a field map based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void copyFieldMap(const stringVect& inputLine);

     //! Create the composite field based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void createComposite(const stringVect& inputLine);

   //! Set the global field based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void setGlobalField(const stringVect& inputLine);

    //! Set the regional (local+global) field based on the info from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void setRegionField(const stringVect& inputLine);

    //! Set the local field only based on information from the inputLine
    /*!
      \param [in] inputLine The space separated input line
    */
    void setLocalField(const stringVect& inputLine);
    

    //! Get the global magnetic field
    /*!
      \returns the global magnetic field pointer
    */
    ShipCompField* getGlobalField() const {return globalField_;}

    //! Get the map storing volume names and their associated local magnetic fields
    /*!
      \returns the map of volume names and their corresponding magnetic field pointers
    */
    SFMap getAllFields() const {return theFields_;}

    //! Get the magnetic field for the given volume
    /*!
      \param [in] volName The name of the TGeo volume
      \returns the pointer of the local magnetic field for the volume
    */
    TVirtualMagField* getVolumeField(const TString& volName) const;

    //! Check if we have a field stored with the given label name
    /*!
      \param [in] label The label name of the field
      \returns a boolean to say if we already have the field stored in the internal map
    */
    Bool_t gotField(const TString& label) const;

    //! Get the field stored with the given label name
    /*!
      \param [in] label The label name of the field
      \returns the pointer to the magnetic field object
    */
    TVirtualMagField* getField(const TString& label) const;

    //! ClassDef for ROOT
    ClassDef(ShipFieldMaker,1);

 
 protected:


 private:

    //! The global magnetic field
    ShipCompField* globalField_;

    //! The map storing all created magnetic fields
    SFMap theFields_;

    //! Double converting Tesla to kiloGauss (for VMC B field units)
    Double_t T_;

    //! Split a string
    /*!
      \param [in] theString The string to be split up
      \param [in] splitted The delimiter that will be used to split up the string
      \returns a vector of the delimiter-separated strings
    */
    stringVect splitString(std::string& theString, std::string& splitter) const;

};

#endif

