import hou, os, re
import shutil
import glob
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import *

# TODO
# Currently this will ignore non-HIP/JOB refs on DOP nodes
# For non-rel files, place images in /tex, geometry in /geo etc rather than /misc?
# Won't work with $WEDGE/$WEDGENUM and probably $ACTIVETAKE

# ===========================================
# Initial Settings Dialog
# ===========================================
class collectSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(collectSettingsDialog, self).__init__()
        self.setWindowTitle("Project Collection Settings")             
        self.setGeometry(300, 300, 400, 100)
        
        sh = hou.ui.qtStyleSheet()
        self.setStyleSheet(sh)
        
        layout = QVBoxLayout()     
        layout.setSpacing(5)        
        layout.setSizeConstraint(QLayout.SetMinimumSize)

        # Checkboxes
        self.ch_a = QCheckBox("Ignore References on Bypassed Nodes")
        self.ch_a .setChecked(True)
        layout.addWidget(self.ch_a)
        
        self.ch_b = QCheckBox("Resolve references outside $HIP/$JOB")
        self.ch_b.setChecked(True)
        layout.addWidget(self.ch_b)             
        
        self.ch_c = QCheckBox("Ignore render proxies (.ifd/.ass/.rs)")
        self.ch_c.setChecked(True)
        layout.addWidget(self.ch_c)   
        
        self.ch_d = QCheckBox("Delete non-Displayed OBJ nodes")
        self.ch_d.setChecked(False)
        layout.addWidget(self.ch_d)    
        
        # Extras TODO
        # Splitter
        line = QFrame();
        line.setFrameShape(QFrame.HLine);
        line.setMinimumSize(0, 20)             
        layout.addWidget(line)      
        
        # Disable archiving
        self.ch_archive = QCheckBox("Disable Archival (Non-HIP/JOB files are just copied to $HIP/misc)")
        self.ch_archive.setChecked(False)
        layout.addWidget(self.ch_archive)    
        
        # File type list
        self.ch_filetype = QCheckBox("File Type Filter (Whitelist)")
        self.ch_filetype.setChecked(False)         

        layout_form = QFormLayout();    
        self.ext = QLineEdit("jpg png exr hdr tiff")
        layout_form.addRow(self.ch_filetype, self.ext);
        self.ext.setEnabled(False)
        layout.addLayout(layout_form)
        # Connect enable/disable to the checkbox
        self.ch_filetype.toggled.connect(self.ext.setEnabled)
                                                
        # ButtonBox
        bbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)    
        bbox.setCenterButtons(True)
        bbox.setMinimumSize(0, 40)   
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
                      
        self.setLayout(layout)      
                
        # Style all checkboxes test
        cbs = self.findChildren(QCheckBox)        
        for w in cbs:
                w.setStyleSheet("""QCheckBox::checked {
                color: #00FF00;
                }""")        
                
                     
    def getValues(self):
        return [self.ch_a.isChecked(), self.ch_b.isChecked(), self.ch_c.isChecked(), self.ch_d.isChecked(), self.ch_archive.isChecked(), self.ch_filetype.isChecked(), self.ext.text()]   
        
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
    
def collectProject(settings):
    IGNORE_BYPASSED = settings[0]
    COPY_NON_RELATIVE = settings[1]
    IGNORE_PROXY = settings[2]
    IGNORE_NONDISPLAY = settings[3]
    DISABLE_ARCHIVE = settings[4]
    FILETYPE_FILTER = settings[5]
    FILETYPES = settings[6]
    
    # save the file, then save it to the collection dir later?
    hou.setUpdateMode(hou.updateMode.Manual)        
    hou.setFrame(hou.playbar.playbackRange()[0])    
    
    hou.hipFile.save()
    hipname = hou.hipFile.basename()    
    refs = hou.fileReferences()
    
    if DISABLE_ARCHIVE:
        collectDir = '$HIP'
    else:
        collectDir = createCollectionDir()
    
    # ignore archived/proxy files
    proxy = ['.ifd', '.ass', '.rs']
    # ignore refs with these extensions for refs not in $HIP or $JOB
    ignoredExt = ['.hda', '.hdalc', '.hdanc', '.otl', '.pc', '.pmap']       
    # filetype whitelist 
    if FILETYPE_FILTER:
        extfilter = ['.' + x for x in FILETYPES.split()]
        
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
            #
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
                # check for file extension filter
                if extfilter and fext in extfilter:
                    if not (r.startswith('$HIP') or r.startswith('$JOB')):
                        if COPY_NON_RELATIVE and fext not in ignoredExt:
                            # Ignore Dop Nodes for now? Also ignore op: refs?
                            if not isinstance(parm.node(), hou.DopNode) and not r.startswith('op'):
                                toCopyMisc.append(ref)    
                    elif not DISABLE_ARCHIVE:
                        toCopy.append(ref) 
    
    # Delete Non-Displayed
    if IGNORE_NONDISPLAY:
        randomNode = hou.node("/").children()[0]
        randomNode.deleteItems(toDel)
                    
    # Create Progress Bar
    numToCopy = len(toCopy) + len(toCopyMisc)
    pbar = QProgressDialog("Copying Files", "Abort", 0, numToCopy);
    pbar.setWindowTitle("Collect Progress")  
    pbar.setWindowModality(Qt.WindowModal);        
    pbar.setStyleSheet(hou.ui.qtStyleSheet())
    l = pbar.layout()
    if l:
        l.setSizeConstraint(QLayout.SetMaximumSize)
    pbar.setValue(0)        
    pbar.forceShow()
                       
    # ==============================================================
    # Copy Relative files HIP/JOB
    # ==============================================================
    if not DISABLE_ARCHIVE:
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
                except Exception as e:
                    pass
                    # print(e)   
    
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
                collectedMiscTemp = collectedMisc + '/' + filename  
                # try to set new parm value
                try:
                    parm.set('$HIP/misc/'+filename)
                except:
                    print "unable to change parm: "+parm.path()
                try:
                    print "Non-$HIP/$JOB File found:" + str(r)                 
                    if not os.path.exists(collectedMiscTemp):
                        print collectedMiscTemp
                        shutil.copy(hou.expandString(r), collectedMiscTemp)             
                except Exception as e:
                    pass
                    # print(e)          
    # set JOB to new HIP loc
    hou.putenv('$JOB', collectDir)

dialog = collectSettingsDialog()
dialog.exec_()
if dialog.result() == 1:
    settings = dialog.getValues()
    collectProject(settings)    
else:
    pass
    # print "Collect Project Cancelled"
