import os
import subprocess
import sys
from utils import load_subjects_list, get_subjects_list_fold
from distutils.version import LooseVersion
import CPAC

pipeline_version = '0.1'


# SUBJECTS LIST FOLD INFO #0-based
fold_n = 0
fold_size = 100

# MOCO PARAMETERS
vols_to_drop = 5

# DENOISE PARAMETERS
hp_cutoff_freq = 0.01
lp_cutoff_freq = 0.1

# STRUCTURAL BRAIN MASK
use_fs_brainmask = True



########################################################################################################################
# SET DIRS
hostname = subprocess.check_output('hostname', shell=True)
arch = subprocess.check_output('arch', shell=True)

print 'working on %s' % hostname
project_root_dir = '/scr/adenauer2/Franz/LeiCA_NKI'
project_root_dir_2 = '/scr/adenauer2/Franz/LeiCA_NKI'

dicom_dir = os.path.join('/scr/kaiser2/NKI/nki_r5_onwards/r6_onwards/dicoms/')
freesurfer_dir = os.path.join('/scr/kaiser2/NKI/nki_r5_onwards/r6_onwards/data/freesurfer')

preprocessed_data_dir = os.path.join(project_root_dir, 'results')
use_n_procs = 3
plugin_name = 'MultiProc'
# plugin_name = 'CondorDAGMan'

fig_dir = '/home/raid2/liem/Dropbox/LeiCa/figs'
report_base_dir = '/home/raid2/liem/Dropbox/LeiCa/QC'
subjects_file_prefix = 'subjects_2015-11-18'
subjects_file = subjects_file_prefix + '_r8.txt'

behav_file = '/home/raid2/liem/Dropbox/LeiCa/sample/20150925_leicanki_sample.pkl'

# TR LIST
TR_list = ['645']



# CHECK IF DIRS EXIST
check_dir_list = [project_root_dir]  # , dicom_dir, freesurfer_dir]
for d in check_dir_list:
    if not os.path.isdir(d):
        raise Exception('Directory %s does not exist. exit pipeline.' % d)

# fixme _metrics
working_dir = os.path.join(project_root_dir_2)
ds_dir = os.path.join(project_root_dir, 'results')

# OTHER STUFF
# set python path
script_dir = os.path.dirname(os.path.realpath(__file__))

# set subjects_dir
subjects_dir = os.path.join(script_dir, 'subjects')

# set template directory
template_dir = os.path.join(script_dir, 'anat_templates')


# APPEND TO PYHTONPATH
prep_script_dir = os.path.join(script_dir, 'preprocessing')
plots_script_dir = os.path.join(script_dir, 'plots')

sys.path.extend([prep_script_dir, plots_script_dir])


# GET SUBJECT LIST FROM TXT FILE
full_subjects_list = load_subjects_list(subjects_dir, subjects_file)
# reduce subjects list to fold
subjects_list = get_subjects_list_fold(full_subjects_list, fold_n, fold_size)



# check pandas version
import pandas as pd

print('Using pandas version %s' % pd.__version__)
if LooseVersion(pd.__version__) >= '0.16':
    print('pandas version OK')
else:
    raise Exception('pandas version >= 0.16 required')

fsl_v_str = subprocess.check_output('cat $FSLDIR/etc/fslversion', shell=True).strip()
print('Using FSL version %s' % fsl_v_str)
if LooseVersion(fsl_v_str) >= '5':
    print('FSL OK')
else:
    raise Exception('FSL >= version 5 required. version %s found' % fsl_v_str)
