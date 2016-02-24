from nipype.pipeline.engine import MapNode, Node, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.io as nio
from preprocessing.utils import tkregister2_fct

import os


def create_struct_preproc_pipeline(working_dir, freesurfer_dir, ds_dir, use_fs_brainmask, name='struct_preproc'):
    """

    """

    # initiate workflow
    struct_preproc_wf = Workflow(name=name)
    struct_preproc_wf.base_dir = os.path.join(working_dir,'LeiCA_resting', 'rsfMRI_preprocessing')
    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # inputnode
    inputnode = Node(util.IdentityInterface(fields=['t1w',
                                                    'subject_id']),
                     name='inputnode')

    # outputnode
    outputnode = Node(util.IdentityInterface(fields=['t1w_brain',
                                                     'struct_brain_mask',
                                                     'fast_partial_volume_files',
                                                     'wm_mask',
                                                     'csf_mask',
                                                     'wm_mask_4_bbr',
                                                     'gm_mask']),
                      name='outputnode')


    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]



    # CREATE BRAIN MASK
    if use_fs_brainmask:
        # brainmask with fs
        fs_source = Node(interface=nio.FreeSurferSource(), name='fs_source')
        fs_source.inputs.subjects_dir = freesurfer_dir
        struct_preproc_wf.connect(inputnode, 'subject_id', fs_source, 'subject_id')

        # get aparc+aseg from list
        def get_aparc_aseg(files):
            for name in files:
                if 'aparc+aseg' in name:
                    return name

        aseg = Node(fs.MRIConvert(out_type='niigz', out_file='aseg.nii.gz'), name='aseg')
        struct_preproc_wf.connect(fs_source, ('aparc_aseg', get_aparc_aseg), aseg, 'in_file')

        fs_brainmask = Node(fs.Binarize(min=0.5, #dilate=1,
                                        out_type='nii.gz'),
                            name='fs_brainmask')
        struct_preproc_wf.connect(aseg, 'out_file', fs_brainmask, 'in_file')


        # fill holes in mask, smooth, rebinarize
        fillholes = Node(fsl.maths.MathsCommand(args='-fillh -s 3 -thr 0.1 -bin',
                                                out_file='T1_brain_mask.nii.gz'),
                         name='fillholes')

        struct_preproc_wf.connect(fs_brainmask, 'binary_file', fillholes, 'in_file')

        fs_2_struct_mat = Node(util.Function(input_names=['moving_image', 'target_image'],
                                             output_names=['fsl_file'],
                                             function=tkregister2_fct),
                               name='fs_2_struct_mat')

        struct_preproc_wf.connect([(fs_source, fs_2_struct_mat, [('T1', 'moving_image'),
                                                      ('rawavg','target_image')])])

        struct_brain_mask =  Node(fsl.ApplyXfm(interp='nearestneighbour'), name='struct_brain_mask_fs')
        struct_preproc_wf.connect(fillholes, 'out_file', struct_brain_mask, 'in_file')
        struct_preproc_wf.connect(inputnode, 't1w', struct_brain_mask, 'reference')
        struct_preproc_wf.connect(fs_2_struct_mat, 'fsl_file', struct_brain_mask, 'in_matrix_file')
        struct_preproc_wf.connect(struct_brain_mask, 'out_file', outputnode, 'struct_brain_mask')
        struct_preproc_wf.connect(struct_brain_mask, 'out_file', ds, 'struct_prep.struct_brain_mask')

        # multiply t1w with fs brain mask
        t1w_brain = Node(fsl.maths.BinaryMaths(operation = 'mul'), name='t1w_brain')
        struct_preproc_wf.connect(inputnode, 't1w', t1w_brain, 'in_file')
        struct_preproc_wf.connect(struct_brain_mask, 'out_file', t1w_brain, 'operand_file')
        struct_preproc_wf.connect(t1w_brain, 'out_file', outputnode, 't1w_brain')
        struct_preproc_wf.connect(t1w_brain, 'out_file',  ds, 'struct_prep.t1w_brain')

    else: # use bet
        t1w_brain = Node(fsl.BET(mask=True, outline=True, surfaces=True), name='t1w_brain')
        struct_preproc_wf.connect(inputnode, 't1w', t1w_brain, 'in_file')
        struct_preproc_wf.connect(t1w_brain, 'out_file', outputnode, 't1w_brain')

        def struct_brain_mask_bet_fct(in_file):
            return in_file
        struct_brain_mask = Node(util.Function(input_names=['in_file'], output_names=['out_file'], function=struct_brain_mask_bet_fct),
                         name='struct_brain_mask')
        struct_preproc_wf.connect(t1w_brain, 'mask_file', struct_brain_mask, 'in_file')
        struct_preproc_wf.connect(struct_brain_mask, 'out_file', outputnode, 'struct_brain_mask')
        struct_preproc_wf.connect(struct_brain_mask, 'out_file', ds, 'struct_prep.struct_brain_mask')



    # SEGMENTATION WITH FAST
    fast = Node(fsl.FAST(), name='fast')
    struct_preproc_wf.connect(t1w_brain, 'out_file', fast, 'in_files')
    struct_preproc_wf.connect(fast, 'partial_volume_files', outputnode, 'fast_partial_volume_files')
    struct_preproc_wf.connect(fast, 'partial_volume_files', ds, 'struct_prep.fast')



    # functions to select tissue classes
    def selectindex(files, idx):
        import numpy as np
        from nipype.utils.filemanip import filename_to_list, list_to_filename
        return list_to_filename(np.array(filename_to_list(files))[idx].tolist())

    def selectsingle(files, idx):
        return files[idx]

    # pve0: CSF
    # pve1: GM
    # pve2: WM
    # binarize tissue classes
    binarize_tissue = MapNode(fsl.ImageMaths(op_string='-nan -thr 0.99 -ero -bin'),
                        iterfield=['in_file'],
                        name='binarize_tissue')

    struct_preproc_wf.connect(fast, ('partial_volume_files', selectindex, [0, 2]), binarize_tissue, 'in_file')



    # OUTPUT  WM AND CSF MASKS FOR CPAC DENOISING
    struct_preproc_wf.connect([(binarize_tissue, outputnode, [(('out_file', selectsingle, 0), 'csf_mask'),
                                                              (('out_file', selectsingle, 1), 'wm_mask')])])



    # WRITE WM MASK WITH P > .5 FOR FSL BBR
    # use threshold of .5 like FSL's epi_reg script
    wm_mask_4_bbr = Node(fsl.ImageMaths(op_string='-thr 0.5 -bin'),  name='wm_mask_4_bbr')
    struct_preproc_wf.connect(fast, ('partial_volume_files', selectindex, [2]), wm_mask_4_bbr, 'in_file')
    struct_preproc_wf.connect(wm_mask_4_bbr, 'out_file', outputnode, 'wm_mask_4_bbr')




    struct_preproc_wf.write_graph(dotfilename=struct_preproc_wf.name, graph2use='flat', format='pdf')

    return struct_preproc_wf

