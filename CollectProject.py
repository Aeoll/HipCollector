import hou, os, re
import shutil
import glob
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2 import QtCore

# TODO
# Currently this will ignore non-HIP/JOB refs on DOP nodes
# For non-rel files, place images in /tex, geometry in /geo etc rather than /misc?
# Won't currently work with $WEDGE/$WEDGENUM and probably $TAKE/$TAKENUM
# QProgressDialog?

# ===========================================
# Initial Settings Dialog
# ===========================================
class collectSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(collectSettingsDialog, self).__init__()
        self.setWindowTitle("Project Collection Settings")     
        self.setStyleSheet(hou.ui.qtStyleSheet())        
        self.setGeometry(300, 300, 350, 300)
        
        layout = QtWidgets.QVBoxLayout()     
        layout.setSpacing(6)        
        layout.setSizeConstraint(QtWidgets.QLayout.SetMaximumSize)

        # Checkboxes
        self.ch_a = QtWidgets.QCheckBox("Ignore References on Bypassed Nodes")
        self.ch_a .setChecked(True)
        layout.addWidget(self.ch_a)
        
        self.ch_b = QtWidgets.QCheckBox("Resolve references outside $HIP/$JOB")
        self.ch_b.setChecked(True)
        layout.addWidget(self.ch_b)             
        
        self.ch_c = QtWidgets.QCheckBox("Ignore render proxies (.ifd/.ass/.rs)")
        self.ch_c.setChecked(True)
        layout.addWidget(self.ch_c)   
        
        self.ch_d = QtWidgets.QCheckBox("Delete non-Displayed OBJ nodes")
        self.ch_d.setChecked(False)
        layout.addWidget(self.ch_d)             
                                   
        # ButtonBox
        bbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)    
        bbox.setCenterButtons(True)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
        
        self.setLayout(layout)      
        
    def getValues(self):
        return [self.ch_a.isChecked(), self.ch_b.isChecked(), self.ch_c.isChecked(), self.ch_d.isChecked()]   
        
# ==============================================================
# Create collection dir in $HIP and avoid overwriting existing
# ==============================================================
def createCollectionDir():
    collectDir = '$HIP'+'/collect'
    counter = 1
    while os.path.exists(hou.expandString(collectDir)) :
        collectDir = '$HIP'+'/collect' + str(counter)
        counter = counter + 1
    collectDir = hou.expandString(collectDir)
    os.makedirs(collectDir)
    return collectDir

def getObjParent(node):
    if isinstance(node, hou.ObjNode):
        return node
    parent = node.parent()
    if not parent:
        return None
    return getObjParent(parent)
    
def collectProject(IGNORE_BYPASSED, COPY_NON_RELATIVE, IGNORE_PROXY, IGNORE_NONDISPLAY):     
    # save the file, then save it to the collection dir later?
    hou.setUpdateMode(hou.updateMode.Manual)        
    hou.setFrame(hou.playbar.playbackRange()[0])    
    
    hou.hipFile.save()
    hipname = hou.hipFile.basename()    
    refs = hou.fileReferences()
    collectDir = createCollectionDir()
        
    # ignore archived/proxy files
    proxy = ['.ifd', '.ass', '.rs']
    # ignore refs with these extensions for refs not in $HIP or $JOB
    ignoredExt = ['.hda', '.hdalc', '.hdanc', '.otl', '.pc', '.pmap']       

    # TODO Also delete non-displayed OBJ nodes when they are ignored?
    toDel = []
    # Get refs to be copied
    toCopy = []
    toCopyMisc = [] # for non-HIP/JOB files to sort out
    for ref in refs:
        parm = ref[0]
        r = ref[1]
        if parm:
            for i in xrange(10): # hack to get referenced parm since isRef is not implemented?
                parm = parm.getReferencedParm()                
            bypassed = parm.node().isGenericFlagSet(hou.nodeFlag.Bypass)
            # Testing for display flag. Could also apply to DOPs but maybe a bad idea..
            disp = True
            if isinstance(parm.node(), hou.SopNode):
                top = getObjParent(parm.node())
                if top:
                    disp = top.isGenericFlagSet(hou.nodeFlag.Display)  
            ##
            if IGNORE_NONDISPLAY and not disp:
                toDel.append(top)
            # copy ref if bypass option is off or node isnt bypassed                  
            elif IGNORE_BYPASSED and bypassed:
                pass
            # copy ref if proxy filter off or ref extension isnt a render proxy                
            elif IGNORE_PROXY and os.path.splitext(r)[1] in proxy:
                pass
            else:
                fname, fext = os.path.splitext(ref[1])
                if not (r.startswith('$HIP') or r.startswith('$JOB')):
                    if COPY_NON_RELATIVE and fext not in ignoredExt:
                        # Ignore Dop Nodes for now? Also ignore op: refs?
                        if (not isinstance(parm.node(), hou.DopNode)) and (not r.startswith('op')):
                            toCopyMisc.append(ref)    
                else:
                    # if not any (ref[1] in rr for rr in toCopy): # we could ignore duplicates here as the parms are not changed?
                    toCopy.append(ref) 
    
    # Delete Non-Displayed
    if IGNORE_NONDISPLAY:
        randomNode = hou.node("/").children()[0]
        randomNode.deleteItems(toDel)
                    
    # Create Progress Bar
    numToCopy = len(toCopy) + len(toCopyMisc)
    pbar = QtWidgets.QProgressDialog("Copying Files", "Abort", 0, numToCopy);
    pbar.setWindowTitle("Collect Progress")  
    pbar.setWindowModality(QtCore.Qt.WindowModal);        
    pbar.setStyleSheet(hou.ui.qtStyleSheet())
    l = pbar.layout()
    if l:
        l.setSizeConstraint(QtWidgets.QLayout.SetMaximumSize)
    pbar.setValue(0)        
    pbar.forceShow()
                       
    # ==============================================================
    # Copy Relative files HIP/JOB
    # ==============================================================
    for ref in toCopy:
        r = ref[1]
        
        # Increment Progress bar. This seems to show the previous item??
        pbar.setValue(pbar.value()+1)
        pbar.setLabelText(r)
        if pbar.wasCanceled():
            break        
        
        # Check if the the ref is linked to another channel. If so, expand that channel value instead (to fix $OS references?)
        parm = ref[0]
        for i in xrange(10): # hack since isRef is not implemented?
            parm = parm.getReferencedParm() 
        r = re.sub('\$OS', parm.node().name(), r)
        
        p = r[4:]
        collectedPath = collectDir + p  
        # ensure the subdir exists in the collect dir        
        collectedDir = os.path.dirname(hou.expandString(collectedPath))
        if not os.path.exists(collectedDir):
            os.makedirs(collectedDir)       
                 
        # Copy Sequences
        if re.search('\$F', r):
            s = re.sub('\$F\d+', '*', r)
            s = re.sub('\$F', '*', s)
            print "$HIP/$JOB Sequence found:" + hou.expandString(s) 
            seqFiles = glob.glob(hou.expandString(s))
            if seqFiles:
                for f in seqFiles:
                    try:
                        copiedFilePath = collectedDir + '/' + os.path.basename(f)                    
                        if not os.path.exists(copiedFilePath):
                            shutil.copy(hou.expandString(f), copiedFilePath) 
                    except:
                        pass
            else:
                print "Error Finding File Sequence - No items copied"
        # Copy Single Files
        else:
            try:
                print "$HIP/$JOB File found:" + str(r)
                if not os.path.exists(collectedPath):
                    shutil.copy(hou.expandString(r), collectedPath)             
            except:
                pass
    
    # save to new loc and sort the non-HIP/JOB refs after saving?   
    hou.hipFile.save(collectDir+'/'+hipname)        
        
    # ==============================================================
    # Copy NON Relative files and adjust their parms
    # ==============================================================   
    if COPY_NON_RELATIVE:
        # Create misc dir
        collectedMisc = ""
        if toCopyMisc:
            collectedMisc = collectDir + '/misc'
            if not os.path.exists(collectedMisc):
                    os.makedirs(collectedMisc)         
    
        for ref in toCopyMisc:
            r = ref[1]

            # Increment Progress bar. This seems to show the previous item??
            pbar.setValue(pbar.value()+1)
            pbar.setLabelText(r)
            if pbar.wasCanceled():
                break        
            
            # Check if the the ref is linked to another channel. If so, expand that channel value instead (to fix $OS references?)
            parm = ref[0]
            for i in xrange(10): # hack since isRef is not implemented?
                parm = parm.getReferencedParm() 
            r = re.sub('\$OS', parm.node().name(), r)
                         
            # Copy Sequences
            if re.search('\$F', r):                
                s = re.sub('\$F\d+', '*', r)
                s = re.sub('\$F', '*', s)
                print "Non-$HIP/$JOB Sequence found:" + hou.expandString(s) 
                seqFiles = glob.glob(hou.expandString(s))
                if seqFiles:
                    # set new parm value (with correct unexpanded $F string?)
                    try:
                        parm.set('$HIP/misc/'+ os.path.basename(r))                
                    except:
                        print "unable to change parm: "+parm.path()
                    for f in seqFiles:
                        try:
                            copiedFilePath = collectedMisc + '/' + os.path.basename(f)                    
                            if not os.path.exists(copiedFilePath):
                                shutil.copy(hou.expandString(f), copiedFilePath) 
                        except:
                            pass
                else:
                    print "Error Finding File Sequence - No items copied"
            # Copy Single Files
            else:
                filename = os.path.basename(hou.expandString(r))
                collectedMisc = collectedMisc + '/' + filename  
                # try to set new parm value
                try:
                    parm.set('$HIP/misc/'+filename)
                except:
                    print "unable to change parm: "+parm.path()
                try:
                    print "Non-$HIP/$JOB File found:" + str(r)                 
                    if not os.path.exists(collectedMisc):
                        shutil.copy(hou.expandString(r), collectedMisc)             
                except:
                    pass
       
    # set JOB to new HIP loc
    hou.putenv('$JOB', collectDir)

dialog = collectSettingsDialog()
dialog.exec_()
if dialog.result() == 1:
    settings = dialog.getValues()
    collectProject(settings[0], settings[1], settings[2], settings[3])    
else:
    pass
    # print "Collect Project Cancelled"