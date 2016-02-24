__author__ = 'franzliem'
# LeiCA preprocessing utils


def tkregister2_fct(moving_image, target_image):
    # don't use nipype tkregister2 interface. typo in nipype 0.10
    # command runs, but creates crashfile
    import os
    fsl_file = os.path.join(os.getcwd(), 'fs_2_struct.mat')
    cmd = 'tkregister2 --noedit --reg register.dat --regheader'
    cmd += ' --mov %s' % moving_image
    cmd += ' --targ %s' % target_image
    cmd += ' --fslregout %s' % fsl_file
    os.system(cmd)
    return fsl_file


def calculate_mean_FD_fct(in_file):
    import os
    import numpy as np

    out_file = os.path.join(os.getcwd(), 'mean_FD.txt')
    FD = np.genfromtxt(in_file)
    mean_FD = FD.mean()

    np.savetxt(out_file, np.array([mean_FD]))

    return (mean_FD, out_file)


def extract_signal_from_tissue(data_file, mask_file):

    '''
    From CPAC 0.3.9
    https://github.com/FCP-INDI/C-PAC/blob/master/CPAC/nuisance/nuisance.py
    extract_tissue_data()

    modified function so that no GM mask is necessary and function extracts tissue for one mask

    '''

    import numpy as np
    import nibabel as nb
    import os
    # fixme
    # from CPAC.utils import safe_shape
    # fixme FL changed
    # from CPAC.utils import safe_shape
    # safe_shape copied from CPAC.utils.utils
    def safe_shape(*vol_data):
        """
        Checks if the volume (first three dimensions) of multiple ndarrays
        are the same shape.

        Parameters
        ----------
        vol_data0, vol_data1, ..., vol_datan : ndarray
            Volumes to check

        Returns
        -------
        same_volume : bool
            True only if all volumes have the same shape.
        """
        same_volume = True

        first_vol_shape = vol_data[0].shape[:3]
        for vol in vol_data[1:]:
            same_volume &= (first_vol_shape == vol.shape[:3])

        return same_volume



    try:
        data = nb.load(data_file).get_data().astype('float64')
    except:
        raise MemoryError('Unable to load %s' % data_file)

    try:
        mask = nb.load(mask_file).get_data().astype('bool')
    except:
        raise MemoryError('Unable to load %s' % mask)

    if not safe_shape(data, mask):
        raise ValueError('Spatial dimensions for data and mask %s do not match' % mask)

    tissue_sigs = data[mask]
    file_sigs = os.path.join(os.getcwd(), 'signals.npy')
    np.save(file_sigs, tissue_sigs)
    del tissue_sigs

    return file_sigs


def time_normalizer(in_file, tr):
    '''
    Mean centering and variance normalizing a time series
    TR in seconds!
    '''
    import os
    import nitime.fmri.io as io
    import nibabel as nib
    from nipype.utils.filemanip import fname_presuffix

    T= io.time_series_from_file(in_file,normalize='zscore', TR=tr)
    normalized_data = T.data

    out_img = nib.Nifti1Image(normalized_data,nib.load(in_file).get_affine())
    out_file = fname_presuffix(in_file, suffix='_norm',newpath=os.getcwd())
    out_img.to_filename(out_file)

    return out_file


def get_aroma_stats_fct(in_dir, subject_id):
    import pandas as pd
    import numpy as np
    import os

    in_file = os.path.join(in_dir, 'classification_overview.txt')
    out_filename = os.path.join(os.getcwd(), 'motion_IC_counts.pkl')

    # import aroma output and cleanup format
    df = pd.read_table(in_file, delimiter="\s", skiprows=1,
                    names=['IC', 'is_motion', 'junk', 'max_rp_corr', 'junk', 'junk', 'edge_fract', 'junk', 'junk', 'hf_content', 'junk', 'junk', 'csf_fract'])
    df = df.drop('junk',1)

    # count motion ICs
    ic_class_count = df.groupby('is_motion').count()
    n_ic = df.IC.max()
    n_motion = ic_class_count.IC[True]
    n_clean = ic_class_count.IC[False]
    df_out = pd.DataFrame([[subject_id, n_ic, n_clean, n_motion]], columns=['ID', 'n_ic', 'n_clean', 'n_motion'])
    df_out = df_out.set_index(df_out.ID)

    df_out.to_pickle(out_filename)

    return out_filename


def fsl_slices_fct(in_file, in_file2):
    '''
    funciton recreates fsl slices command
    '''
    import os

    out_file_montage = os.path.join(os.getcwd(), 'slices.png')
    out_list = []
    out_file = os.path.join(os.getcwd(), 'slices_0.png')
    out_list += [out_file]
    cmd = 'slicer ' + in_file + ' ' + in_file2 + ' -a ' + out_file
    os.system(cmd)
    png_str = 'pngappend %s ' % out_file

    ax_list = ['x', 'y', 'z']
    slice_pos_list = [.3,.4,.5,.6,7]
    i = 1
    for ax in ax_list:
        new_line = True
        for slice_pos in slice_pos_list:
            if new_line:
                png_str += '- ' #new line
                new_line = False
            else:
                png_str += '+ ' #cont. line

            out_file = os.path.join(os.getcwd(), 'slices_%s.png' % i)
            out_list += [out_file]
            cmd = 'slicer ' + in_file + ' ' + in_file2 + ' -%s %s '%(ax,slice_pos) + out_file
            os.system(cmd)
            png_str += '%s ' % out_file
            i += 1
    png_str += out_file_montage
    os.system(png_str)
    return out_file_montage

