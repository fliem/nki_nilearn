from nibabel import gifti
import h5py
import numpy as np

subjects = []
with open('/scr/ilz1/nilearn_vol2surf_sink/subjects.txt') as f:
    subjects = f.read().splitlines()
hemis = ['rh', 'lh']
smooths = ['fwhm0', 'fwhm6']

fname_template = '/scr/ilz1/nilearn_vol2surf_sink/%s/%s_%s_preprocessed_fsaverage5_%s.gii'

for smooth in smooths:
    for sub in subjects: 
        for hemi in hemis: 
            print smooth, sub, hemi
        
            fname=fname_template%(smooth, sub, hemi, smooth)
            gii=gifti.giftiio.read(fname)
            mat=np.zeros((gii.darrays[0].data.shape[0], len(gii.darrays)))
            for arr in range(len(gii.darrays)):
                mat[:,arr]=gii.darrays[arr].data
                
            hname=fname[:-3]+'hdf5'
            f = h5py.File(hname, 'w')
            f.create_dataset('mat', data=mat)
            f.close()
