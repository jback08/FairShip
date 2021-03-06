import os,ROOT,MufluxPatRec,charmDet_conf
import shipunit as u
import rootUtils as ut

import sys, os

from array import array
from ShipGeoConfig import ConfigRegistry

import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt
import numpy as np

stop  = ROOT.TVector3()
start = ROOT.TVector3()

# geoFile   = 'geofile_full.conical.PGplus-TGeant4.root'
#geoFile   = '/eos/experiment/ship/data/muflux/run_fixedtarget/19april2018/geofile_full.root'
#fgeo = ROOT.TFile(geoFile)
#sGeo = fgeo.FAIRGeom


class MufluxDigiReco:
    " convert FairSHiP MC hits / digitized hits to measurements"
    def __init__(self,fout,fgeo):

        self.iEvent = 0
        self.sGeo = fgeo.FAIRGeom

        outdir=os.getcwd()
        outfile=outdir+"/"+fout
        self.fn = ROOT.TFile(fout,'update')
        self.sTree = self.fn.cbmsim

        if self.sTree.GetBranch("FitTracks"):
            print "remove RECO branches and rerun reconstruction"
            self.fn.Close()
            # make a new file without reco branches
            f = ROOT.TFile(fout)
            sTree = f.cbmsim
            if sTree.GetBranch("FitTracks"): sTree.SetBranchStatus("FitTracks",0)
            if sTree.GetBranch("Particles"): sTree.SetBranchStatus("Particles",0)
            if sTree.GetBranch("fitTrack2MC"): sTree.SetBranchStatus("fitTrack2MC",0)
            if sTree.GetBranch("FitTracks_PR"): sTree.SetBranchStatus("FitTracks_PR",0)
            if sTree.GetBranch("Particles_PR"): sTree.SetBranchStatus("Particles_PR",0)
            if sTree.GetBranch("fitTrack2MC_PR"): sTree.SetBranchStatus("fitTrack2MC_PR",0)
            if sTree.GetBranch("MufluxSpectrometerPoint"):
                if sTree.GetBranch("Digi_MufluxSpectrometerHits"):
                    sTree.SetBranchStatus("Digi_MufluxSpectrometerHits",0)

            rawFile = fout.replace("_rec.root","_raw.root")
            recf = ROOT.TFile(rawFile,"recreate")
            newTree = sTree.CloneTree(0)
            for n in range(sTree.GetEntries()):
                sTree.GetEntry(n)
                rc = newTree.Fill()
            sTree.Clear()
            newTree.AutoSave()
            f.Close()
            recf.Close()
            os.system('cp '+rawFile +' '+fout)
            self.fn = ROOT.TFile(fout,'update')
            self.sTree     = self.fn.cbmsim

        #  check that all containers are present, otherwise create dummy version
        """
        self.dummyContainers={}
        branch_class = {"MufluxSpectrometerPoint":"MufluxSpectrometerPoint","MuonTaggerPoint":"MuonTaggerPoint"}
        for x in branch_class:
            if not self.sTree.GetBranch(x):
                self.dummyContainers[x+"_array"] = ROOT.TClonesArray(branch_class[x])
                self.dummyContainers[x] = self.sTree.Branch(x,self.dummyContainers[x+"_array"],32000,-1)
                setattr(self.sTree,x,self.dummyContainers[x+"_array"])
                self.dummyContainers[x].Fill()
        """
        if self.sTree.GetBranch("GeoTracks"): self.sTree.SetBranchStatus("GeoTracks",0)

        # prepare for output
        # event header
        self.header  = ROOT.FairEventHeader()
        self.eventHeader  = self.sTree.Branch("ShipEventHeader",self.header,32000,-1)
        # fitted tracks
        self.fGenFitArray = ROOT.TClonesArray("genfit::Track")
        self.fGenFitArray.BypassStreamer(ROOT.kFALSE)
        self.fitTrack2MC  = ROOT.std.vector('int')()
        self.mcLink      = self.sTree.Branch("fitTrack2MC"+realPR,self.fitTrack2MC,32000,-1)
        self.fitTracks   = self.sTree.Branch("FitTracks"+realPR,  self.fGenFitArray,32000,-1)

        if self.sTree.GetBranch("MufluxSpectrometerPoint"):
            self.digiMufluxSpectrometer    = ROOT.TClonesArray("MufluxSpectrometerHit")
            self.digiMufluxSpectrometerBranch   = self.sTree.Branch("Digi_MufluxSpectrometerHits",self.digiMufluxSpectrometer,32000,-1)
        # for the digitizing step
        self.v_drift = modules["MufluxSpectrometer"].TubeVdrift()
        self.sigma_spatial = modules["MufluxSpectrometer"].TubeSigmaSpatial()
        self.viewangle = modules["MufluxSpectrometer"].ViewAngle()

        # setup random number generator
        self.random = ROOT.TRandom()
        ROOT.gRandom.SetSeed(13)
        self.PDG = ROOT.TDatabasePDG.Instance()

        # access ShipTree
        self.sTree.GetEvent(0)
        self.geoMat =  ROOT.genfit.TGeoMaterialInterface()
        # init geometry and mag. field
        gMan  = ROOT.gGeoManager
        #import geomGeant4
        #shipGeo = ConfigRegistry.loadpy("$FAIRSHIP/geometry/charm-geometry_config.py")
        #fieldMaker = geomGeant4.addVMCFields(shipGeo, 'field/GoliathBFieldSetup.txt', False)
        #geomGeant4.printVMCFields()
        self.bfield = ROOT.genfit.FairShipFields()
        self.fM = ROOT.genfit.FieldManager.getInstance()
        self.fM.init(self.bfield)

        ROOT.genfit.MaterialEffects.getInstance().init(self.geoMat)

        # init fitter, to be done before importing shipPatRec
        self.fitter      = ROOT.genfit.DAF()

        if debug:

            # self.fitter.setDebugLvl(1) # produces lot of printout
            output_dir = 'pics/'
            if os.path.exists(output_dir):
                print('The directiry is already exists. It is OK.')
            else:
                os.mkdir(output_dir)

    # for 'real' PatRec
    #shipPatRec.initialize(fgeo)

    def reconstruct(self):
        ntracks = self.findTracks()

    def digitize(self):

        if not self.sTree.GetBranch("MufluxSpectrometerPoint"):
            if self.sTree.GetBranch("Digi_MufluxSpectrometerHits"):
                self.digiMufluxSpectrometer = self.sTree.Digi_MufluxSpectrometerHits
                return

        self.sTree.t0 = self.random.Rndm()*1*u.microsecond
        self.header.SetEventTime( self.sTree.t0 )
        self.header.SetRunId( self.sTree.MCEventHeader.GetRunID() )
        self.header.SetMCEntryNumber( self.sTree.MCEventHeader.GetEventID() )  # counts from 1
        self.eventHeader.Fill()
        self.digiMufluxSpectrometer.Delete()
        self.digitizeMufluxSpectrometer()
        self.digiMufluxSpectrometerBranch.Fill()


    def digitizeMufluxSpectrometer(self):

        # digitize FairSHiP MC hits
        index = 0
        hitsPerDetId = {}

        for aMCPoint in self.sTree.MufluxSpectrometerPoint:
            aHit = ROOT.MufluxSpectrometerHit(aMCPoint,self.sTree.t0)
            if self.digiMufluxSpectrometer.GetSize() == index: self.digiMufluxSpectrometer.Expand(index+1000)
            self.digiMufluxSpectrometer[index]=aHit
            detID = aHit.GetDetectorID()
            if hitsPerDetId.has_key(detID):
                if self.digiMufluxSpectrometer[hitsPerDetId[detID]].tdc() > aHit.tdc():
                    # second hit with smaller tdc
                    self.digiMufluxSpectrometer[hitsPerDetId[detID]].setInvalid()
                    hitsPerDetId[detID] = index
            else:
                hitsPerDetId[detID] = index
            index+=1

        T1_entries_px = {}
        T4_entries_px = {}
        nMufluxHits = self.sTree.MufluxSpectrometerPoint.GetEntriesFast()
        for i in range(nMufluxHits):
            MufluxHit = self.sTree.MufluxSpectrometerPoint[i]
            detector = self.sGeo.FindNode(MufluxHit.GetX(),MufluxHit.GetY(),MufluxHit.GetZ()).GetName()
            MufluxTrackId = MufluxHit.GetTrackID()
            pid = MufluxHit.PdgCode()
            xcoord = MufluxHit.GetX()
            ycoord = MufluxHit.GetY()
            if abs(pid)==13:
                if (detector[0:8]=="gas_12_1"):
                    rc=h['hits-T1'].Fill(xcoord,ycoord)
                if (detector[0:9]=="gas_12_10"):
                    rc=h['hits-T1x'].Fill(xcoord,ycoord)
                if (detector[0:9]=="gas_12_11"):
                    rc=h['hits-T1u'].Fill(xcoord,ycoord)
                if (detector[0:8]=="gas_12_2"):
                    rc=h['hits-T2'].Fill(xcoord,ycoord)
                if (detector[0:9]=="gas_12_20"):
                    rc=h['hits-T2v'].Fill(xcoord,ycoord)
                if (detector[0:9]=="gas_12_21"):
                    rc=h['hits-T2x'].Fill(xcoord,ycoord)
                if (detector[0:5]=="gas_3"):
                    rc=h['hits-T3'].Fill(xcoord,ycoord)
                if (detector[0:5]=="gas_4"):
                    rc=h['hits-T4'].Fill(xcoord,ycoord)

            if (detector[0:9]=="gas_12_10"):
                if T1_entries_px.has_key(MufluxTrackId):
                    continue
                else:
                    if abs(pid)==13 :
                        T1_entries_px[MufluxTrackId]=[MufluxHit.GetPx()]

            if (detector[0:5]=="gas_4"):
                if T4_entries_px.has_key(MufluxTrackId):
                    continue
                else:
                    pid = MufluxHit.PdgCode()
                if abs(pid)==13 :
                    T4_entries_px[MufluxTrackId]=[MufluxHit.GetPx()]

        for i in range(nMufluxHits):
            MufluxHit = self.sTree.MufluxSpectrometerPoint[i]
            MufluxTrackId = MufluxHit.GetTrackID()
            if (T1_entries_px.get(MufluxTrackId) is None or T4_entries_px.get(MufluxTrackId) is None) :
                continue
            else:
                rc=h['pt-kick'].Fill(T1_entries_px.get(MufluxTrackId)[0]-T4_entries_px.get(MufluxTrackId)[0])

    def withT0Estimate(self):
        # loop over all straw tdcs and make average, correct for ToF
        n = 0
        t0 = 0.
        key = -1
        SmearedHits = []
        v_drift = modules["MufluxSpectrometer"].TubeVdrift()
        z1 = stop.z()
        for aDigi in self.digiMufluxSpectrometer:
            key+=1
            if not aDigi.isValid: continue
            detID = aDigi.GetDetectorID()
            # don't use hits from straw veto
            station = int(detID/10000000)
            if station > 4 : continue
            aDigi.MufluxSpectrometerEndPoints(start,stop)
            # MufluxSpectrometerHit::MufluxSpectrometerEndPoints(TVector3 &vbot, TVector3 &vtop)
            delt1 = (start[2]-z1)/u.speedOfLight
            t0+=aDigi.GetDigi()-delt1
            SmearedHits.append( {'digiHit':key,'xtop':stop.x(),'ytop':stop.y(),'z':stop.z(),'xbot':start.x(),'ybot':start.y(),'dist':aDigi.GetDigi(), 'detID':detID} )
            n+=1
        if n>0:
            t0 = t0/n - 73.2*u.ns
            print "t0 ",t0
        for s in SmearedHits:
            delt1 = (s['z']-z1)/u.speedOfLight
            s['dist'] = (s['dist'] -delt1 -t0)*v_drift
            print "s['dist']",s['dist']
        return SmearedHits

    def smearHits(self,no_amb=None):
        # smear strawtube points
        SmearedHits = []
        key = -1
        for ahit in self.sTree.MufluxSpectrometerPoint:
            key+=1
            detID = ahit.GetDetectorID()
            top = ROOT.TVector3()
            bot = ROOT.TVector3()
            modules["MufluxSpectrometer"].TubeEndPoints(detID,bot,top)
            # MufluxSpectrometerHit::MufluxSpectrometerEndPoints(TVector3 &vbot, TVector3 &vtop)
            #distance to wire, and smear it.
            dw  = ahit.dist2Wire()
            smear = dw
            if not no_amb:
                smear = abs(self.random.Gaus(dw,self.sigma_spatial))

            SmearedHits.append( {'digiHit':key,'xtop':top.x(),'ytop':top.y(),'z':top.z(),'xbot':bot.x(),'ybot':bot.y(),'dist':smear, 'detID':detID} )
            # Note: top.z()==bot.z() unless misaligned, so only add key 'z' to smearedHit

            if abs(top.y())==abs(bot.y()): h['disty'].Fill(dw)
            if abs(top.y())>abs(bot.y()): h['distu'].Fill(dw)
            if abs(top.y())<abs(bot.y()): h['distv'].Fill(dw)

        return SmearedHits


    def smearHits_realData(self):

        # smear strawtube points
        SmearedHits = []
        key = -1
        for ahit in self.sTree.Digi_MufluxSpectrometerHits:
            key+=1
            detID = ahit.GetDetectorID()
            top = ROOT.TVector3()
            bot = ROOT.TVector3()
            ahit.MufluxSpectrometerEndPoints(bot,top)
            # MufluxSpectrometerHit::MufluxSpectrometerEndPoints(TVector3 &vbot, TVector3 &vtop)
            # distance to wire.
            dist  = ahit.GetDigi() * 3.7 / (2000. * 2.)

            SmearedHits.append( {'digiHit':key,'xtop':top.x(),'ytop':top.y(),'z':top.z(),'xbot':bot.x(),'ybot':bot.y(),'dist':dist, 'detID':detID} )

            if abs(top.y())==abs(bot.y()): h['disty'].Fill(dist)
            if abs(top.y())>abs(bot.y()): h['distu'].Fill(dist)
            if abs(top.y())<abs(bot.y()): h['distv'].Fill(dist)

        return SmearedHits


    def getPtruthFirst(self,mcPartKey):
        Ptruth,Ptruthx,Ptruthy,Ptruthz = -1.,-1.,-1.,-1.
        for ahit in self.sTree.MufluxSpectrometerPoint:
            if ahit.GetTrackID() == mcPartKey:
                Ptruthx,Ptruthy,Ptruthz = ahit.GetPx(),ahit.GetPy(),ahit.GetPz()
                Ptruth  = ROOT.TMath.Sqrt(Ptruthx**2+Ptruthy**2+Ptruthz**2)
                break
        return Ptruth,Ptruthx,Ptruthy,Ptruthz

    def getPtruthAtOrigin(self,mcPartKey):
        Ptruth,Ptruthx,Ptruthy,Ptruthz = -1.,-1.,-1.,-1.
        atrack=self.sTree.MCTrack[mcPartKey]
        Ptruthx= atrack.GetPx()
        Ptruthy= atrack.GetPy()
        Ptruthz= atrack.GetPz()
        Ptruth  = ROOT.TMath.Sqrt(Ptruthx**2+Ptruthy**2+Ptruthz**2)
        return Ptruth,Ptruthx,Ptruthy,Ptruthz


    def fracMCsame(self, trackids):

        track = {}
        nh = len(trackids)

        for tid in trackids:
            if track.has_key(tid):
                track[tid] += 1
            else:
                track[tid] = 1

        # now get track with largest number of hits
        if track != {}:
            tmax = max(track, key=track.get)
        else:
            track = {-999:0}
            tmax = -999

        frac = 0.
        if nh > 0:
            frac = float(track[tmax]) / float(nh)

        return frac,tmax


    def recognition_metrics(self, track_hit_ids, mode='all'):

        n_tracks_y12 = 0
        n_recognized_y12 = 0
        n_clones_y12 = 0
        n_ghosts_y12 = 0
        n_others_y12 = 0

        n_tracks_stereo12 = 0
        n_recognized_stereo12 = 0
        n_clones_stereo12 = 0
        n_ghosts_stereo12 = 0
        n_others_stereo12 = 0

        n_tracks_34 = 0
        n_recognized_34 = 0
        n_clones_34 = 0
        n_ghosts_34 = 0
        n_others_34 = 0

        true_track_ids_y12 = []
        true_track_ids_stereo12 = []
        true_track_ids_34 = []

        n_true_track_hits_y12 = {}
        n_true_track_hits_stereo12 = {}
        n_true_track_hits_34 = {}

        n_true_track_hits_1 = {}
        n_true_track_hits_2 = {}
        n_true_track_hits_3 = {}
        n_true_track_hits_4 = {}

        for ahit in self.sTree.MufluxSpectrometerPoint:

            track_id = ahit.GetTrackID()

            detID = ahit.GetDetectorID()
            statnb = detID // 10000000
            vnb = (detID - statnb * 10000000) // 1000000

            is_y12 = (statnb == 1) * (vnb == 0) + (statnb == 2) * (vnb == 1)
            is_stereo12 = (statnb == 1) * (vnb == 1) + (statnb == 2) * (vnb == 0)
            is_34 = (statnb == 3) + (statnb == 4)

            if statnb == 1:
                if n_true_track_hits_1.has_key(track_id):
                    n_true_track_hits_1[track_id] += 1
                else:
                    n_true_track_hits_1[track_id] = 1

            if statnb == 2:
                if n_true_track_hits_2.has_key(track_id):
                    n_true_track_hits_2[track_id] += 1
                else:
                    n_true_track_hits_2[track_id] = 1

            if statnb == 3:
                if n_true_track_hits_3.has_key(track_id):
                    n_true_track_hits_3[track_id] += 1
                else:
                    n_true_track_hits_3[track_id] = 1

            if statnb == 4:
                if n_true_track_hits_4.has_key(track_id):
                    n_true_track_hits_4[track_id] += 1
                else:
                    n_true_track_hits_4[track_id] = 1

            if is_y12:
                if n_true_track_hits_y12.has_key(track_id):
                    n_true_track_hits_y12[track_id] += 1
                else:
                    n_true_track_hits_y12[track_id] = 1

            if is_stereo12:
                if n_true_track_hits_stereo12.has_key(track_id):
                    n_true_track_hits_stereo12[track_id] += 1
                else:
                    n_true_track_hits_stereo12[track_id] = 1

            if is_34:
                if n_true_track_hits_34.has_key(track_id):
                    n_true_track_hits_34[track_id] += 1
                else:
                    n_true_track_hits_34[track_id] = 1


        if mode == 'all':
            min_hits = 1
        elif mode == '3hits':
            min_hits = 3

        if mode == 'all' or mode == '3hits':
            for key in n_true_track_hits_y12.keys():
                if n_true_track_hits_y12[key] >= min_hits:
                    true_track_ids_y12.append(key)

            for key in n_true_track_hits_stereo12.keys():
                if n_true_track_hits_stereo12[key] >= min_hits:
                    true_track_ids_stereo12.append(key)

            for key in n_true_track_hits_34.keys():
                if n_true_track_hits_34[key] >= min_hits:
                    true_track_ids_34.append(key)

        if mode == 'Tr4':
            min_hits = 1
            for key in n_true_track_hits_y12.keys():
                if n_true_track_hits_1.has_key(key) and n_true_track_hits_2.has_key(key):
                    if n_true_track_hits_3.has_key(key) and n_true_track_hits_4.has_key(key):
                        if n_true_track_hits_y12[key] >= min_hits:
                            true_track_ids_y12.append(key)

            for key in n_true_track_hits_stereo12.keys():
                if n_true_track_hits_1.has_key(key) and n_true_track_hits_2.has_key(key):
                    if n_true_track_hits_3.has_key(key) and n_true_track_hits_4.has_key(key):
                        if n_true_track_hits_stereo12[key] >= min_hits:
                            true_track_ids_stereo12.append(key)

            for key in n_true_track_hits_34.keys():
                if n_true_track_hits_1.has_key(key) and n_true_track_hits_2.has_key(key):
                    if n_true_track_hits_3.has_key(key) and n_true_track_hits_4.has_key(key):
                        if n_true_track_hits_34[key] >= min_hits:
                            true_track_ids_34.append(key)



        n_tracks_y12 = len(true_track_ids_y12)
        n_tracks_stereo12 = len(true_track_ids_stereo12)
        n_tracks_34 = len(true_track_ids_34)

        found_track_ids_y12 = []
        found_track_ids_stereo12 = []
        found_track_ids_34 = []

        for i_track in track_hit_ids.keys():

            atrack = track_hit_ids[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            if len(atrack_y12) > 0:
                reco_hit_ids_y12 = []
                for i_hit in atrack_y12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_y12.append(ahit.GetTrackID())
                frac_y12, tmax_y12 = self.fracMCsame(reco_hit_ids_y12)
                if frac_y12 >= 0.7:
                    if tmax_y12 in true_track_ids_y12 and tmax_y12 not in found_track_ids_y12:
                        n_recognized_y12 += 1
                        found_track_ids_y12.append(tmax_y12)
                    elif tmax_y12 in true_track_ids_y12 and tmax_y12 in found_track_ids_y12:
                        n_clones_y12 += 1
                    elif tmax_y12 not in true_track_ids_y12:
                        n_others_y12 += 1
                else:
                    n_ghosts_y12 += 1


            if len(atrack_stereo12) > 0:
                reco_hit_ids_stereo12 = []
                for i_hit in atrack_stereo12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_stereo12.append(ahit.GetTrackID())
                frac_stereo12, tmax_stereo12 = self.fracMCsame(reco_hit_ids_stereo12)
                if frac_stereo12 >= 0.7:
                    if tmax_stereo12 in true_track_ids_stereo12 and tmax_stereo12 not in found_track_ids_stereo12:
                        n_recognized_stereo12 += 1
                        found_track_ids_stereo12.append(tmax_stereo12)
                    elif tmax_stereo12 in true_track_ids_stereo12 and tmax_stereo12 in found_track_ids_stereo12:
                        n_clones_stereo12 += 1
                    elif tmax_stereo12 not in true_track_ids_stereo12:
                        n_others_stereo12 += 1
                else:
                    n_ghosts_stereo12 += 1


            if len(atrack_34) > 0:
                reco_hit_ids_34 = []
                for i_hit in atrack_34:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_34.append(ahit.GetTrackID())
                frac_34, tmax_34 = self.fracMCsame(reco_hit_ids_34)
                if frac_34 >= 0.7:
                    if tmax_34 in true_track_ids_34 and tmax_34 not in found_track_ids_34:
                        n_recognized_34 += 1
                        found_track_ids_34.append(tmax_34)
                    elif tmax_34 in true_track_ids_34 and tmax_34 in found_track_ids_34:
                        n_clones_34 += 1
                    elif tmax_34 not in true_track_ids_34:
                        n_others_34 += 1
                else:
                    n_ghosts_34 += 1

        output = (n_tracks_y12, n_recognized_y12, n_clones_y12, n_ghosts_y12, n_others_y12,
                  n_tracks_stereo12, n_recognized_stereo12, n_clones_stereo12, n_ghosts_stereo12, n_others_stereo12,
                  n_tracks_34, n_recognized_34, n_clones_34, n_ghosts_34, n_others_34)

        return output


    def target_metrics(self, track_hit_ids):

        n_tracks = 0
        n_recognized = 0
        n_clones = 0
        n_ghosts = 0
        n_others = 0

        true_track_ids = []

        n_true_track_hits_y12 = {}
        n_true_track_hits_stereo12 = {}
        n_true_track_hits_34 = {}

        for ahit in self.sTree.MufluxSpectrometerPoint:

            track_id = ahit.GetTrackID()

            detID = ahit.GetDetectorID()
            statnb = detID // 10000000
            vnb = (detID - statnb * 10000000) // 1000000

            is_y12 = (statnb == 1) * (vnb == 0) + (statnb == 2) * (vnb == 1)
            is_stereo12 = (statnb == 1) * (vnb == 1) + (statnb == 2) * (vnb == 0)
            is_34 = (statnb == 3) + (statnb == 4)

            if is_y12:
                if n_true_track_hits_y12.has_key(track_id):
                    n_true_track_hits_y12[track_id] += 1
                else:
                    n_true_track_hits_y12[track_id] = 1

            if is_stereo12:
                if n_true_track_hits_stereo12.has_key(track_id):
                    n_true_track_hits_stereo12[track_id] += 1
                else:
                    n_true_track_hits_stereo12[track_id] = 1

            if is_34:
                if n_true_track_hits_34.has_key(track_id):
                    n_true_track_hits_34[track_id] += 1
                else:
                    n_true_track_hits_34[track_id] = 1

        min_hits = 3
        for key in n_true_track_hits_y12.keys():
            if n_true_track_hits_y12[key] >= min_hits:
                if n_true_track_hits_stereo12.has_key(key):
                    if n_true_track_hits_stereo12[key] >= min_hits:
                        if n_true_track_hits_34.has_key(key):
                            if n_true_track_hits_34[key] >= min_hits:
                                true_track_ids.append(key)

        n_tracks = len(true_track_ids)

        found_track_ids = []

        for i_track in track_hit_ids.keys():

            atrack = track_hit_ids[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            if len(atrack_y12) >= min_hits and len(atrack_stereo12) >= min_hits and len(atrack_34) >= min_hits:

                reco_hit_ids_y12 = []
                for i_hit in atrack_y12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_y12.append(ahit.GetTrackID())
                frac_y12, tmax_y12 = self.fracMCsame(reco_hit_ids_y12)

                reco_hit_ids_stereo12 = []
                for i_hit in atrack_stereo12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_stereo12.append(ahit.GetTrackID())
                frac_stereo12, tmax_stereo12 = self.fracMCsame(reco_hit_ids_stereo12)

                reco_hit_ids_34 = []
                for i_hit in atrack_34:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_34.append(ahit.GetTrackID())
                frac_34, tmax_34 = self.fracMCsame(reco_hit_ids_34)

                min_eff = 0.7
                if tmax_y12 == tmax_stereo12 and tmax_y12 == tmax_34:
                    if frac_y12 >= min_eff and frac_stereo12 >= min_eff and frac_34 >= min_eff:

                        if tmax_y12 in true_track_ids and tmax_y12 not in found_track_ids:
                            n_recognized += 1
                            found_track_ids.append(tmax_y12)
                        elif tmax_y12 in true_track_ids and tmax_y12 in found_track_ids:
                            n_clones += 1
                        elif tmax_y12 not in true_track_ids:
                            n_others += 1

                    else:
                        n_ghosts += 1
                else:
                    n_ghosts += 1

            else:
                n_ghosts += 1

        output = (n_tracks, n_recognized, n_clones, n_ghosts, n_others)

        return output


    def all_tracks_metrics(self, track_hit_ids):

        n_tracks = 0
        n_recognized = 0
        n_clones = 0
        n_ghosts = 0
        n_others = 0

        true_track_ids = []
        for ahit in self.sTree.MufluxSpectrometerPoint:
            track_id = ahit.GetTrackID()
            if track_id not in true_track_ids:
                true_track_ids.append(track_id)

        n_tracks = len(true_track_ids)
        found_track_ids = []
        min_hits = 3

        for i_track in track_hit_ids.keys():

            atrack = track_hit_ids[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            if len(atrack_y12) >= min_hits and len(atrack_stereo12) >= min_hits and len(atrack_34) >= min_hits:

                reco_hit_ids_y12 = []
                for i_hit in atrack_y12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_y12.append(ahit.GetTrackID())
                frac_y12, tmax_y12 = self.fracMCsame(reco_hit_ids_y12)

                reco_hit_ids_stereo12 = []
                for i_hit in atrack_stereo12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_stereo12.append(ahit.GetTrackID())
                frac_stereo12, tmax_stereo12 = self.fracMCsame(reco_hit_ids_stereo12)

                reco_hit_ids_34 = []
                for i_hit in atrack_34:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_34.append(ahit.GetTrackID())
                frac_34, tmax_34 = self.fracMCsame(reco_hit_ids_34)

                min_eff = 0.7
                if tmax_y12 == tmax_stereo12 and tmax_y12 == tmax_34:
                    if frac_y12 >= min_eff and frac_stereo12 >= min_eff and frac_34 >= min_eff:

                        if tmax_y12 in true_track_ids and tmax_y12 not in found_track_ids:
                            n_recognized += 1
                            found_track_ids.append(tmax_y12)
                        elif tmax_y12 in true_track_ids and tmax_y12 in found_track_ids:
                            n_clones += 1
                        elif tmax_y12 not in true_track_ids:
                            n_others += 1

                    else:
                        n_ghosts += 1
                else:
                    n_ghosts += 1

            else:
                n_ghosts += 1

        output = (n_tracks, n_recognized, n_clones, n_ghosts, n_others)

        return output


    def muon_metrics(self, track_hit_ids):

        n_tracks = 0
        n_recognized = 0
        n_clones = 0
        n_ghosts = 0
        n_others = 0

        true_track_ids = []
        for ahit in self.sTree.MufluxSpectrometerPoint:
            track_id = ahit.GetTrackID()
            pdg = ahit.PdgCode()
            if track_id not in true_track_ids:
                if abs(pdg)==13:
                    true_track_ids.append(track_id)

        n_tracks = len(true_track_ids)
        found_track_ids = []
        min_hits = 3

        for i_track in track_hit_ids.keys():

            atrack = track_hit_ids[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            if len(atrack_y12) >= min_hits and len(atrack_stereo12) >= min_hits and len(atrack_34) >= min_hits:

                reco_hit_ids_y12 = []
                for i_hit in atrack_y12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_y12.append(ahit.GetTrackID())
                frac_y12, tmax_y12 = self.fracMCsame(reco_hit_ids_y12)

                reco_hit_ids_stereo12 = []
                for i_hit in atrack_stereo12:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_stereo12.append(ahit.GetTrackID())
                frac_stereo12, tmax_stereo12 = self.fracMCsame(reco_hit_ids_stereo12)

                reco_hit_ids_34 = []
                for i_hit in atrack_34:
                    ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                    reco_hit_ids_34.append(ahit.GetTrackID())
                frac_34, tmax_34 = self.fracMCsame(reco_hit_ids_34)

                min_eff = 0.7
                if tmax_y12 == tmax_stereo12 and tmax_y12 == tmax_34:
                    if frac_y12 >= min_eff and frac_stereo12 >= min_eff and frac_34 >= min_eff:

                        if tmax_y12 in true_track_ids and tmax_y12 not in found_track_ids:
                            n_recognized += 1
                            found_track_ids.append(tmax_y12)
                        elif tmax_y12 in true_track_ids and tmax_y12 in found_track_ids:
                            n_clones += 1
                        elif tmax_y12 not in true_track_ids:
                            n_others += 1

                    else:
                        n_ghosts += 1
                else:
                    n_ghosts += 1

            else:
                n_ghosts += 1

        output = (n_tracks, n_recognized, n_clones, n_ghosts, n_others)

        return output


    def muon_metrics_vs_p(self, track_hit_ids):

        n_tracks = 0
        n_recognized = 0
        n_clones = 0
        n_ghosts = 0
        n_others = 0

        true_track_ids = []
        true_track_p = {}
        for ahit in self.sTree.MufluxSpectrometerPoint:
            track_id = ahit.GetTrackID()
            pdg = ahit.PdgCode()
            if track_id not in true_track_ids:
                if abs(pdg)==13:
                    true_track_ids.append(track_id)
            if not true_track_p.has_key(track_id):
                Ptruth,Ptruthx,Ptruthy,Ptruthz = self.getPtruthFirst(track_id)
                true_track_p[track_id] = Ptruth
                h['True_all_tracks_vs_p_true'].Fill(Ptruth)
                if abs(pdg)==13:
                    h['True_muons_vs_p_true'].Fill(Ptruth)

        n_tracks = len(true_track_ids)
        found_track_ids = []
        min_hits = 3

        for i_track in track_hit_ids.keys():

            atrack = track_hit_ids[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            reco_hit_ids_y12 = []
            for i_hit in atrack_y12:
                ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                reco_hit_ids_y12.append(ahit.GetTrackID())
            frac_y12, tmax_y12 = self.fracMCsame(reco_hit_ids_y12)

            reco_hit_ids_stereo12 = []
            for i_hit in atrack_stereo12:
                ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                reco_hit_ids_stereo12.append(ahit.GetTrackID())
            frac_stereo12, tmax_stereo12 = self.fracMCsame(reco_hit_ids_stereo12)

            reco_hit_ids_34 = []
            for i_hit in atrack_34:
                ahit = self.sTree.MufluxSpectrometerPoint[i_hit['digiHit']]
                reco_hit_ids_34.append(ahit.GetTrackID())
            frac_34, tmax_34 = self.fracMCsame(reco_hit_ids_34)

            if len(atrack_y12) >= min_hits and len(atrack_stereo12) >= min_hits and len(atrack_34) >= min_hits:

                min_eff = 0.7
                if tmax_y12 == tmax_stereo12 and tmax_y12 == tmax_34:
                    if frac_y12 >= min_eff and frac_stereo12 >= min_eff and frac_34 >= min_eff:

                        if tmax_y12 in true_track_ids and tmax_y12 not in found_track_ids:
                            n_recognized += 1
                            found_track_ids.append(tmax_y12)
                            h['Reco_muons_vs_p_true'].Fill(true_track_p[tmax_y12])
                        elif tmax_y12 in true_track_ids and tmax_y12 in found_track_ids:
                            n_clones += 1
                        elif tmax_y12 not in true_track_ids:
                            n_others += 1

                    else:
                        n_ghosts += 1
                        h['Ghosts_muons_vs_p_true'].Fill(true_track_p[tmax_y12])
                else:
                    n_ghosts += 1
                    h['Ghosts_muons_vs_p_true'].Fill(true_track_p[tmax_y12])

            else:
                n_ghosts += 1
                h['Ghosts_muons_vs_p_true'].Fill(true_track_p[tmax_y12])

        output = (n_tracks, n_recognized, n_clones, n_ghosts, n_others)

        return output



    def findTracks(self):

        hitPosLists    = {}
        hitPosLists_noT4    = {}
        stationCrossed = {}
        stationCrossed_noT4 = {}
        trackDigiHits = {}
        trackDigiHits_noT4 = {}
        trackCandidates = []
        trackCandidates_noT4 = []
        nTrack = -1

        self.fGenFitArray.Delete()
        self.fitTrack2MC.clear()

        # hit smearing
        if self.sTree.GetBranch("MufluxSpectrometerPoint"):
            if withT0:
                self.SmearedHits = self.withT0Estimate()
            else:
                self.SmearedHits = self.smearHits(withNoStrawSmearing)
        elif self.sTree.GetBranch("Digi_MufluxSpectrometerHits"):
            self.SmearedHits = self.smearHits_realData()
        else:
            print('No branches "MufluxSpectrometer" or "Digi_MufluxSpectrometerHits".')
            return nTrack

        if realPR:

            # Do real PatRec
            track_hits = MufluxPatRec.execute(self.SmearedHits)

            # Create hitPosLists for track fit
            for i_track in track_hits.keys():

                atrack = track_hits[i_track]
                atrack_y12 = atrack['y12']
                atrack_stereo12 = atrack['stereo12']
                atrack_34 = atrack['34']
                atrack_smeared_hits = list(atrack_y12) + list(atrack_stereo12) + list(atrack_34)

                for sm in atrack_smeared_hits:

                    detID = self.digiMufluxSpectrometer[sm['digiHit']].GetDetectorID()
                    station = int(detID/10000000)
                    trID = i_track

                    # T1-4 for track fit
                    if not hitPosLists.has_key(trID):
                        hitPosLists[trID] = ROOT.std.vector('TVectorD')()
                        stationCrossed[trID] = {}
                        trackDigiHits[trID] = []
                    m = array('d',[sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist']])
                    hitPosLists[trID].push_back(ROOT.TVectorD(7,m))
                    if not stationCrossed[trID].has_key(station):
                        stationCrossed[trID][station]=0
                    stationCrossed[trID][station]+=1
                    trackDigiHits[trID].append(sm['digiHit'])

                    # T1-3 for track fit
                    if (int(detID/1000000)!=40):
                        if not hitPosLists_noT4.has_key(trID):
                            hitPosLists_noT4[trID]     = ROOT.std.vector('TVectorD')()
                            stationCrossed_noT4[trID]  = {}
                            trackDigiHits_noT4[trID] = []
                        m_noT4 = array('d',[sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist']])
                        hitPosLists_noT4[trID].push_back(ROOT.TVectorD(7,m_noT4))
                        if not stationCrossed_noT4[trID].has_key(station):
                            stationCrossed_noT4[trID][station]=0
                        stationCrossed_noT4[trID][station]+=1
                        trackDigiHits_noT4[trID].append(sm['digiHit'])

        # Do fake PatRec
        else:

            if not self.sTree.GetBranch("MufluxSpectrometerPoint"):
                print('Fake PatRec is impossible. No "MufluxSpectrometerPoint" branch.')
                return nTrack

            track_hits = {}
            for sm in self.SmearedHits:

                detID = self.digiMufluxSpectrometer[sm['digiHit']].GetDetectorID()
                station = int(detID/10000000)
                vnb = (detID - station * 10000000) // 1000000
                is_y12 = (station == 1) * (vnb == 0) + (station == 2) * (vnb == 1)
                is_stereo12 = (station == 1) * (vnb == 1) + (station == 2) * (vnb == 0)
                is_34 = (station == 3) + (station == 4)

                trID = self.sTree.MufluxSpectrometerPoint[sm['digiHit']].GetTrackID()

                # PatRec
                if not track_hits.has_key(trID):
                    atrack = {'y12': [], 'stereo12': [], '34': []}
                    track_hits[trID] = atrack
                if is_y12:
                    track_hits[trID]['y12'].append(sm)
                if is_stereo12:
                    track_hits[trID]['stereo12'].append(sm)
                if is_34:
                    track_hits[trID]['34'].append(sm)

                # T1-4 for track fit
                if not hitPosLists.has_key(trID):
                    hitPosLists[trID] = ROOT.std.vector('TVectorD')()
                    stationCrossed[trID]  = {}
                    trackDigiHits[trID] = []
                m = array('d',[sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist']])
                hitPosLists[trID].push_back(ROOT.TVectorD(7,m))
                if not stationCrossed[trID].has_key(station):
                    stationCrossed[trID][station]=0
                stationCrossed[trID][station]+=1
                trackDigiHits[trID].append(sm['digiHit'])

                # T1-3 for track fit
                if (int(detID/1000000)!=40):
                    if not hitPosLists_noT4.has_key(trID):
                        hitPosLists_noT4[trID] = ROOT.std.vector('TVectorD')()
                        stationCrossed_noT4[trID]  = {}
                        trackDigiHits_noT4[trID] = []
                    m_noT4 = array('d',[sm['xtop'],sm['ytop'],sm['z'],sm['xbot'],sm['ybot'],sm['z'],sm['dist']])
                    hitPosLists_noT4[trID].push_back(ROOT.TVectorD(7,m_noT4))
                    if not stationCrossed_noT4[trID].has_key(station):
                        stationCrossed_noT4[trID][station]=0
                    stationCrossed_noT4[trID][station]+=1
                    trackDigiHits_noT4[trID].append(sm['digiHit'])


        # T1-4 track fit
        for atrack in hitPosLists:

            if atrack < 0:
                continue # these are hits not assigned to MC track because low E cut
            pdg = 13 # only muons
            if not abs(pdg)==13:
                continue # only keep muons

            meas = hitPosLists[atrack]
            nM = meas.size()

            #if nM < 12 : continue                          # not enough hits to make a good trackfit
            #comment for hits in t1-3
            if len(stationCrossed[atrack]) < 4 :
                continue  # not enough stations crossed to make a good trackfit

            charge = self.PDG.GetParticle(pdg).Charge()/(3.)
            posM = ROOT.TVector3(0, 0, 0)
            momM = ROOT.TVector3(0,0,3.*u.GeV)
            # approximate covariance
            covM = ROOT.TMatrixDSym(6)
            resolution = self.sigma_spatial
            if withT0:
                resolution = resolution*1.4 # worse resolution due to t0 estimate
            for i in range(3):
                covM[i][i] = resolution*resolution
            covM[0][0]=resolution*resolution*100.
            for i in range(3,6):
                covM[i][i] = ROOT.TMath.Power(resolution / nM / ROOT.TMath.Sqrt(3), 2)
            # trackrep
            rep = ROOT.genfit.RKTrackRep(pdg)
            # smeared start state
            stateSmeared = ROOT.genfit.MeasuredStateOnPlane(rep)
            rep.setPosMomCov(stateSmeared, posM, momM, covM)
            # create track
            seedState = ROOT.TVectorD(6)
            seedCov   = ROOT.TMatrixDSym(6)
            rep.get6DStateCov(stateSmeared, seedState, seedCov)
            theTrack = ROOT.genfit.Track(rep, seedState, seedCov)
            hitCov = ROOT.TMatrixDSym(7)
            hitCov[6][6] = resolution*resolution
            for m in meas:
                tp = ROOT.genfit.TrackPoint(theTrack) # note how the point is told which track it belongs to
                measurement = ROOT.genfit.WireMeasurement(m,hitCov,1,6,tp) # the measurement is told which trackpoint it belongs to
                measurement.setMaxDistance(1.85*u.cm)
                # measurement.setLeftRightResolution(-1)
                tp.addRawMeasurement(measurement) # package measurement in the TrackPoint
                theTrack.insertPoint(tp)  # add point to Track
            trackCandidates.append([theTrack,atrack])

        # T1-3 track fit
        for atrack in hitPosLists_noT4:

            if atrack < 0:
                continue # these are hits not assigned to MC track because low E cut
            pdg = 13 # only muons
            if not abs(pdg)==13:
                continue # only keep muons
            meas = hitPosLists_noT4[atrack]
            nM = meas.size()

            #if nM < 6 : continue                          # not enough hits to make a good trackfit
            #comment for hits in t1-3
            if len(stationCrossed[atrack]) < 3 :
                continue  # not enough stations crossed to make a good trackfit

            charge = self.PDG.GetParticle(pdg).Charge()/(3.)
            posM = ROOT.TVector3(0, 0, 0)
            momM = ROOT.TVector3(0,0,3.*u.GeV)
            # approximate covariance
            covM = ROOT.TMatrixDSym(6)
            resolution = self.sigma_spatial
            if withT0:
                resolution = resolution*1.4 # worse resolution due to t0 estimate
            for i in range(3):
                covM[i][i] = resolution*resolution
            covM[0][0]=resolution*resolution*100.
            for i in range(3,6):
                covM[i][i] = ROOT.TMath.Power(resolution / nM / ROOT.TMath.Sqrt(3), 2)
            # trackrep
            rep = ROOT.genfit.RKTrackRep(pdg)
            # smeared start state
            stateSmeared = ROOT.genfit.MeasuredStateOnPlane(rep)
            rep.setPosMomCov(stateSmeared, posM, momM, covM)
            # create track
            seedState = ROOT.TVectorD(6)
            seedCov   = ROOT.TMatrixDSym(6)
            rep.get6DStateCov(stateSmeared, seedState, seedCov)
            theTrack = ROOT.genfit.Track(rep, seedState, seedCov)
            hitCov = ROOT.TMatrixDSym(7)
            hitCov[6][6] = resolution*resolution
            for m in meas:
                tp = ROOT.genfit.TrackPoint(theTrack) # note how the point is told which track it belongs to
                measurement = ROOT.genfit.WireMeasurement(m,hitCov,1,6,tp) # the measurement is told which trackpoint it belongs to
                measurement.setMaxDistance(1.85*u.cm)
                # measurement.setLeftRightResolution(-1)
                tp.addRawMeasurement(measurement) # package measurement in the TrackPoint
                theTrack.insertPoint(tp)  # add point to Track
            trackCandidates_noT4.append([theTrack,atrack])

        if debug:

            z_hits_y = []
            x_hits_y = []
            for ahit in self.SmearedHits:
                detID = ahit['detID']
                station = int(detID/10000000)
                vnb = (detID - station * 10000000) // 1000000
                is_y12 = (station == 1) * (vnb == 0) + (station == 2) * (vnb == 1)
                is_stereo12 = (station == 1) * (vnb == 1) + (station == 2) * (vnb == 0)
                is_34 = (station == 3) + (station == 4)
                if is_y12 or is_34:
                    z_hits_y.append(ahit['z'])
                    x_hits_y.append(ahit['xtop'])
            plt.figure(figsize=(11, 6))
            plt.scatter(z_hits_y, x_hits_y, color='b')
            for i_track in track_hits:
                atrack = track_hits[i_track]
                atrack_y12 = atrack['y12']
                atrack_stereo12 = atrack['stereo12']
                atrack_34 = atrack['34']
                atrack_y = list(atrack_y12) + list(atrack_34)
                z_atrack_y = [ahit['z'] for ahit in atrack_y]
                x_atrack_y = [ahit['xtop'] for ahit in atrack_y]
                plt.scatter(z_atrack_y, x_atrack_y, color=np.random.rand(3,))
            plt.xlabel('z')
            plt.ylabel('x')
            plt.xlim(0, 1000)
            plt.ylim(-150, 150)
            plt.savefig('pics/event_'+str(self.iEvent)+'.pdf', format='pdf', bbox_inches='tight')
            plt.clf()
            plt.close()





        # Metrics
        if self.sTree.GetBranch("MufluxSpectrometerPoint"):


            (n_tracks, n_recognized, n_clones, n_ghosts, n_others) = self.target_metrics(track_hits)
            h['Reco_target'].Fill("N total", n_tracks)
            h['Reco_target'].Fill("N recognized tracks", n_recognized)
            h['Reco_target'].Fill("N clones", n_clones)
            h['Reco_target'].Fill("N ghosts", n_ghosts)
            h['Reco_target'].Fill("N others", n_others)

            (n_tracks, n_recognized, n_clones, n_ghosts, n_others) = self.muon_metrics(track_hits)
            h['Reco_muon'].Fill("N total", n_tracks)
            h['Reco_muon'].Fill("N recognized tracks", n_recognized)
            h['Reco_muon'].Fill("N clones", n_clones)
            h['Reco_muon'].Fill("N ghosts", n_ghosts)
            h['Reco_muon'].Fill("N others", n_others)

            (n_tracks, n_recognized, n_clones, n_ghosts, n_others) = self.muon_metrics_vs_p(track_hits)

            (n_tracks, n_recognized, n_clones, n_ghosts, n_others) = self.all_tracks_metrics(track_hits)
            h['Reco_all_tracks'].Fill("N total", n_tracks)
            h['Reco_all_tracks'].Fill("N recognized tracks", n_recognized)
            h['Reco_all_tracks'].Fill("N clones", n_clones)
            h['Reco_all_tracks'].Fill("N ghosts", n_ghosts)
            h['Reco_all_tracks'].Fill("N others", n_others)


            (n_tracks_y12, n_recognized_y12, n_clones_y12, n_ghosts_y12, n_others_y12,
             n_tracks_stereo12, n_recognized_stereo12, n_clones_stereo12, n_ghosts_stereo12, n_others_stereo12,
             n_tracks_34, n_recognized_34, n_clones_34, n_ghosts_34, n_others_34) = self.recognition_metrics(track_hits)

            h['NTrueTracks'].Fill("Stations 1&2, Y views", n_tracks_y12)
            h['NTrueTracks'].Fill("Stations 1&2, Stereo views", n_tracks_stereo12)
            h['NTrueTracks'].Fill("Stations 3&4", n_tracks_34)

            h['Reco_y12'].Fill("N total", n_tracks_y12)
            h['Reco_y12'].Fill("N recognized tracks", n_recognized_y12)
            h['Reco_y12'].Fill("N clones", n_clones_y12)
            h['Reco_y12'].Fill("N ghosts", n_ghosts_y12)
            h['Reco_y12'].Fill("N others", n_others_y12)

            h['Reco_stereo12'].Fill("N total", n_tracks_stereo12)
            h['Reco_stereo12'].Fill("N recognized tracks", n_recognized_stereo12)
            h['Reco_stereo12'].Fill("N clones", n_clones_stereo12)
            h['Reco_stereo12'].Fill("N ghosts", n_ghosts_stereo12)
            h['Reco_stereo12'].Fill("N others", n_others_stereo12)

            h['Reco_34'].Fill("N total", n_tracks_34)
            h['Reco_34'].Fill("N recognized tracks", n_recognized_34)
            h['Reco_34'].Fill("N clones", n_clones_34)
            h['Reco_34'].Fill("N ghosts", n_ghosts_34)
            h['Reco_34'].Fill("N others", n_others_34)


            (n_tracks_y12, n_recognized_y12, n_clones_y12, n_ghosts_y12, n_others_y12,
             n_tracks_stereo12, n_recognized_stereo12, n_clones_stereo12, n_ghosts_stereo12, n_others_stereo12,
             n_tracks_34, n_recognized_34, n_clones_34, n_ghosts_34, n_others_34) = self.recognition_metrics(track_hits, mode='3hits')

            h['NTrueTracks_3hits'].Fill("Stations 1&2, Y views", n_tracks_y12)
            h['NTrueTracks_3hits'].Fill("Stations 1&2, Stereo views", n_tracks_stereo12)
            h['NTrueTracks_3hits'].Fill("Stations 3&4", n_tracks_34)

            h['Reco_y12_3hits'].Fill("N total", n_tracks_y12)
            h['Reco_y12_3hits'].Fill("N recognized tracks", n_recognized_y12)
            h['Reco_y12_3hits'].Fill("N clones", n_clones_y12)
            h['Reco_y12_3hits'].Fill("N ghosts", n_ghosts_y12)
            h['Reco_y12_3hits'].Fill("N others", n_others_y12)

            h['Reco_stereo12_3hits'].Fill("N total", n_tracks_stereo12)
            h['Reco_stereo12_3hits'].Fill("N recognized tracks", n_recognized_stereo12)
            h['Reco_stereo12_3hits'].Fill("N clones", n_clones_stereo12)
            h['Reco_stereo12_3hits'].Fill("N ghosts", n_ghosts_stereo12)
            h['Reco_stereo12_3hits'].Fill("N others", n_others_stereo12)

            h['Reco_34_3hits'].Fill("N total", n_tracks_34)
            h['Reco_34_3hits'].Fill("N recognized tracks", n_recognized_34)
            h['Reco_34_3hits'].Fill("N clones", n_clones_34)
            h['Reco_34_3hits'].Fill("N ghosts", n_ghosts_34)
            h['Reco_34_3hits'].Fill("N others", n_others_34)


            (n_tracks_y12, n_recognized_y12, n_clones_y12, n_ghosts_y12, n_others_y12,
             n_tracks_stereo12, n_recognized_stereo12, n_clones_stereo12, n_ghosts_stereo12, n_others_stereo12,
             n_tracks_34, n_recognized_34, n_clones_34, n_ghosts_34, n_others_34) = self.recognition_metrics(track_hits, mode='Tr4')

            h['NTrueTracks_Tr4'].Fill("Stations 1&2, Y views", n_tracks_y12)
            h['NTrueTracks_Tr4'].Fill("Stations 1&2, Stereo views", n_tracks_stereo12)
            h['NTrueTracks_Tr4'].Fill("Stations 3&4", n_tracks_34)

            h['Reco_y12_Tr4'].Fill("N total", n_tracks_y12)
            h['Reco_y12_Tr4'].Fill("N recognized tracks", n_recognized_y12)
            h['Reco_y12_Tr4'].Fill("N clones", n_clones_y12)
            h['Reco_y12_Tr4'].Fill("N ghosts", n_ghosts_y12)
            h['Reco_y12_Tr4'].Fill("N others", n_others_y12)

            h['Reco_stereo12_Tr4'].Fill("N total", n_tracks_stereo12)
            h['Reco_stereo12_Tr4'].Fill("N recognized tracks", n_recognized_stereo12)
            h['Reco_stereo12_Tr4'].Fill("N clones", n_clones_stereo12)
            h['Reco_stereo12_Tr4'].Fill("N ghosts", n_ghosts_stereo12)
            h['Reco_stereo12_Tr4'].Fill("N others", n_others_stereo12)

            h['Reco_34_Tr4'].Fill("N total", n_tracks_34)
            h['Reco_34_Tr4'].Fill("N recognized tracks", n_recognized_34)
            h['Reco_34_Tr4'].Fill("N clones", n_clones_34)
            h['Reco_34_Tr4'].Fill("N ghosts", n_ghosts_34)
            h['Reco_34_Tr4'].Fill("N others", n_others_34)



            n_true_track_hits_y12 = {}
            n_true_track_hits_stereo12 = {}
            n_true_track_hits_34 = {}
            for ahit in self.sTree.MufluxSpectrometerPoint:

                track_id = ahit.GetTrackID()

                detID = ahit.GetDetectorID()
                statnb = detID // 10000000
                vnb = (detID - statnb * 10000000) // 1000000

                is_y12 = (statnb == 1) * (vnb == 0) + (statnb == 2) * (vnb == 1)
                is_stereo12 = (statnb == 1) * (vnb == 1) + (statnb == 2) * (vnb == 0)
                is_34 = (statnb == 3) + (statnb == 4)

                if is_y12:
                    if n_true_track_hits_y12.has_key(track_id):
                        n_true_track_hits_y12[track_id] += 1
                    else:
                        n_true_track_hits_y12[track_id] = 1
                if is_stereo12:
                    if n_true_track_hits_stereo12.has_key(track_id):
                        n_true_track_hits_stereo12[track_id] += 1
                    else:
                        n_true_track_hits_stereo12[track_id] = 1
                if is_34:
                    if n_true_track_hits_34.has_key(track_id):
                        n_true_track_hits_34[track_id] += 1
                    else:
                        n_true_track_hits_34[track_id] = 1

            for key in n_true_track_hits_y12.keys():
                n = n_true_track_hits_y12[key]
                h['NHits_true_y12'].Fill(n)
            for key in n_true_track_hits_stereo12.keys():
                n = n_true_track_hits_stereo12[key]
                h['NHits_true_stereo12'].Fill(n)
            for key in n_true_track_hits_34.keys():
                n = n_true_track_hits_34[key]
                h['NHits_true_34'].Fill(n)

        for i_track in track_hits.keys():
            atrack = track_hits[i_track]
            atrack_y12 = atrack['y12']
            atrack_stereo12 = atrack['stereo12']
            atrack_34 = atrack['34']

            if len(atrack_y12) > 0:
                h['NHits_reco_y12'].Fill(len(atrack_y12))
            if len(atrack_stereo12) > 0:
                h['NHits_reco_stereo12'].Fill(len(atrack_stereo12))
            if len(atrack_34) > 0:
                h['NHits_reco_34'].Fill(len(atrack_34))




        for entry in trackCandidates:
            #check
            #print "fitting with stereo"
            atrack = entry[1]
            theTrack = entry[0]
            if not theTrack.checkConsistency():
                print 'Problem with track before fit, not consistent',atrack,theTrack
                continue
            # do the fit
            try:  self.fitter.processTrack(theTrack) # processTrackWithRep(theTrack,rep,True)
            except:
                print "genfit failed to fit track"
                continue
            #check
            if not theTrack.checkConsistency():
                #print 'Problem with track after fit, not consistent',atrack,theTrack
                continue
            fitStatus   = theTrack.getFitStatus()
            nmeas = fitStatus.getNdf()
            chi2        = fitStatus.getChi2()/nmeas
            pvalue = fitStatus.getPVal()
            #if pvalue < 0.05:
            #  print "P value too low. Rejecting track."
            #  continue
            h['nmeas'].Fill(nmeas)
            h['chi2'].Fill(chi2)
            h['p-value'].Fill(pvalue)
            try:
                fittedState = theTrack.getFittedState()
                fittedMom = fittedState.getMomMag()
                h['p-fittedtracks'].Fill(fittedMom)
                h['1/p-fittedtracks'].Fill(1./fittedMom)
                Px,Py,Pz = fittedState.getMom().x(),fittedState.getMom().y(),fittedState.getMom().z()
                P = fittedMom
                Pt = ROOT.TMath.Sqrt(Px*Px+Py*Py)
                h['p/pt'].Fill(P,Pt)

                if self.sTree.GetBranch("MufluxSpectrometerPoint"):

                    atrack_ids = []
                    for digi_hit in trackDigiHits[atrack]:
                        ahit = self.sTree.MufluxSpectrometerPoint[digi_hit]
                        atrack_ids.append(ahit.GetTrackID())
                    frac, tmax = self.fracMCsame(atrack_ids)
                    Ptruth,Ptruthx,Ptruthy,Ptruthz = self.getPtruthFirst(tmax) # MC Truth
                    Pgun,Pgunx,Pguny,Pgunz = self.getPtruthAtOrigin(tmax) # MC Truth
                    Pttruth = ROOT.TMath.Sqrt(Ptruthx*Ptruthx+Ptruthy*Ptruthy)
                    h['p/pt_truth'].Fill(Ptruth,Pttruth)
                    perr = (P - Ptruth) / Ptruth
                    pterr = (Pt - Pttruth) / Pttruth
                    h['p_rel_error'].Fill(perr)
                    h['pt_rel_error'].Fill(pterr)

                    if Pz !=0:
                        pxpzfitted = Px/Pz
                        pypzfitted = Py/Pz
                        if Ptruthz !=0:
                            pxpztrue = Ptruthx/Ptruthz
                            pypztrue = Ptruthy/Ptruthz
                            h['Px/Pzfitted'].Fill(pxpzfitted)
                            h['Py/Pzfitted'].Fill(pypzfitted)
                            h['Px/Pztrue'].Fill(pxpztrue)
                            h['Py/Pztrue'].Fill(pypztrue)
                            h['Px/Pzfitted-Px/Pztruth'].Fill(Ptruth,pxpzfitted-pxpztrue)
                            h['Py/Pzfitted-Py/Pztruth'].Fill(Ptruth,pypzfitted-pypztrue)
                    h['ptruth'].Fill(Ptruth)
                    delPOverP = (P/Ptruth)-1
                    invdelPOverP = (Ptruth/P)-1
                    if 1==0:
                        if invdelPOverP < -0.8:
                            print "invdelPOverP = ",invdelPOverP
                            print "Ptruth =",Ptruth," Pfitted =",P
                            for n in range(hitPosLists[atrack].size()):
                                print "hit=",n," x(top) ",hitPosLists[atrack][n][0]," y(top) ",hitPosLists[atrack][n][1]," z ",hitPosLists[atrack][n][2]," x(bot) ",hitPosLists[atrack][n][3]," y(bot) ", hitPosLists[atrack][n][4], " dist ", hitPosLists[atrack][n][6]
                                nMufluxHits = self.sTree.MufluxSpectrometerPoint.GetEntriesFast()
                                for i in range(nMufluxHits):
                                    MufluxHit = self.sTree.MufluxSpectrometerPoint[i]
                                    if ((hitPosLists[atrack][n][0]+1.8 > MufluxHit.GetX()) or(hitPosLists[atrack][n][3]+1.8 > MufluxHit.GetX())) and ((hitPosLists[atrack][n][0]-1.8<MufluxHit.GetX()) or (hitPosLists[atrack][n][3]-1.8<MufluxHit.GetX())) and (hitPosLists[atrack][n][2]+1.>MufluxHit.GetZ()) and (hitPosLists[atrack][n][2]-1.<MufluxHit.GetZ()):
                                        print "hit x=",MufluxHit.GetX()," y=",MufluxHit.GetY()," z=",MufluxHit.GetZ()


                    h['delPOverP'].Fill(Ptruth,delPOverP)
                    h['invdelPOverP'].Fill(Ptruth,invdelPOverP)
                    h['deltaPOverP'].Fill(Ptruth,delPOverP)
                    h['Pfitted-Pgun'].Fill(Pgun,P)
                    #print "end fitting with stereo"

            except:
                print "problem with fittedstate"
                continue

                #if 1==0:
        for entry in trackCandidates_noT4:
            #check
            #print "fitting without stereo hits"
            atrack = entry[1]
            theTrack = entry[0]
            if not theTrack.checkConsistency():
                print 'Problem with track before fit, not consistent',atrack,theTrack
                continue
            # do the fit
            try:  self.fitter.processTrack(theTrack) # processTrackWithRep(theTrack,rep,True)
            except:
                print "genfit failed to fit track"
                continue
            #check
            if not theTrack.checkConsistency():
                print 'Problem with track after fit, not consistent',atrack,theTrack
                continue
            fitStatus   = theTrack.getFitStatus()
            nmeas = fitStatus.getNdf()
            chi2        = fitStatus.getChi2()/nmeas
            pvalue = fitStatus.getPVal()
            #if pvalue < 0.05:
            #  print "P value too low. Rejecting track."
            #  continue
            h['nmeas-noT4'].Fill(nmeas)
            h['chi2-noT4'].Fill(chi2)
            h['p-value-noT4'].Fill(pvalue)
            try:

                fittedState = theTrack.getFittedState()
                fittedMom = fittedState.getMomMag()
                h['p-fittedtracks-noT4'].Fill(fittedMom)
                h['1/p-fittedtracks-noT4'].Fill(1./fittedMom)
                Px,Py,Pz = fittedState.getMom().x(),fittedState.getMom().y(),fittedState.getMom().z()
                P = fittedMom
                Pt = ROOT.TMath.Sqrt(Px*Px+Py*Py)
                h['p/pt_noT4'].Fill(P,Pt)

                if self.sTree.GetBranch("MufluxSpectrometerPoint"):

                    atrack_ids = []
                    for digi_hit in trackDigiHits_noT4[atrack]:
                        ahit = self.sTree.MufluxSpectrometerPoint[digi_hit]
                        atrack_ids.append(ahit.GetTrackID())
                    frac, tmax = self.fracMCsame(atrack_ids)
                    Ptruth,Ptruthx,Ptruthy,Ptruthz = self.getPtruthFirst(tmax)
                    Pgun,Pgunx,Pguny,Pgunz = self.getPtruthAtOrigin(tmax)
                    Pttruth = ROOT.TMath.Sqrt(Ptruthx*Ptruthx+Ptruthy*Ptruthy)
                    h['p/pt_truth_noT4'].Fill(Ptruth,Pttruth)
                    perr = (P - Ptruth) / Ptruth
                    pterr = (Pt - Pttruth) / Pttruth
                    h['p_rel_error_noT4'].Fill(perr)
                    h['pt_rel_error_noT4'].Fill(pterr)

                    if Pz !=0:
                        pxpzfitted = Px/Pz
                        pypzfitted = Py/Pz
                        if Ptruthz !=0:
                            pxpztrue = Ptruthx/Ptruthz
                            pypztrue = Ptruthy/Ptruthz
                            h['Px/Pzfitted-Px/Pztruth-noT4'].Fill(Ptruth,pxpzfitted-pxpztrue)
                            h['Py/Pzfitted-Py/Pztruth-noT4'].Fill(Ptruth,pypzfitted-pypztrue)
                            h['Px/Pzfitted-noT4'].Fill(pxpzfitted)
                            h['Py/Pzfitted-noT4'].Fill(pypzfitted)
                            h['Px/Pztrue-noT4'].Fill(pxpztrue)
                            h['Py/Pztrue-noT4'].Fill(pypztrue)

                    h['ptruth-noT4'].Fill(Ptruth)
                    delPOverP = (P/Ptruth)-1
                    invdelPOverP = (Ptruth/P)-1
                    h['delPOverP-noT4'].Fill(Ptruth,delPOverP)
                    h['invdelPOverP-noT4'].Fill(Ptruth,invdelPOverP)
                    h['deltaPOverP-noT4'].Fill(Ptruth,delPOverP)
                    h['Pfitted-Pgun-noT4'].Fill(Pgun,P)
                    #print "end fitting without stereo hits"
            except:
                print "noT4 track: problem with fittedstate"
                continue

            # make track persistent
            nTrack   = self.fGenFitArray.GetEntries()
            if not debug:
                theTrack.prune("CFL")  #  http://sourceforge.net/p/genfit/code/HEAD/tree/trunk/core/include/Track.h#l280
            self.fGenFitArray[nTrack] = theTrack
            self.fitTrack2MC.push_back(atrack)
            if debug:
                print 'save track',theTrack,chi2,nM,fitStatus.isFitConverged()
        self.fitTracks.Fill()
        self.mcLink.Fill()
        return nTrack+1

    def finish(self):
        del self.fitter
        print 'finished writing tree'
        self.sTree.Write()
        ut.errorSummary()
        h['p/pt_truth_noT4'].Draw('colz')
        h['p/pt_truth'].Draw('colz')
        h['p/pt'].Draw('colz')
        h['p/pt_noT4'].Draw('colz')
        ut.writeHists(h,"recohists.root")
        # if realPR: ut.writeHists(shipPatRec.h,"recohists_patrec.root")


