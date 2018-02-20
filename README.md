# HipCollector
A Houdini script which collects a .hip and it's file references into a single portable directory

# Usage
The tool is packaged with Aelib https://github.com/Aeoll/Aelib 
Available in the aelib shelf under 'Collect Project'
To use independently of Aelib, download and copy the code into a new Shelf Tool.

# Settings
Ignore References on Bypassed Nodes
If checked references on bypassed nodes will not be copied into the collection folder
Resolve references outside $HIP/$JOB
If checked files not referenced from $HIP/$JOB will be copied to /misc in the collection folder and the parameters referencing these will be updated 
Ignore render proxies
If checked references to files with the extensions shown will be ignored

# Limitations
Probably doesn't work for references with these variables: $TAKE / $TAKENUM / $WEDGE / $WEDGENUM / $SLICE
