__author__ = 'franzliem'
from nipype.pipeline.engine import Node, Workflow, MapNode
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
import nipype.interfaces.freesurfer as freesurfer
import nipype.interfaces.io as nio
from nipype.algorithms.metrics import Similarity
from preprocessing.utils import tkregister2_fct
from utils import fsl_slices_fct

import os


def create_registration_pipeline(working_dir, freesurfer_dir, ds_dir, name='registration'):
    """
    find transformations between struct, funct, and MNI
    """

    # initiate workflow
    reg_wf = Workflow(name=name)
    reg_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting', 'rsfMRI_preprocessing')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')
    freesurfer.FSCommand.set_default_subjects_dir(freesurfer_dir)

    # inputnode
    inputnode = Node(util.IdentityInterface(fields=['initial_mean_epi_moco',
                                                    't1w',
                                                    't1w_brain',
                                                    'subject_id',
                                                    'wm_mask_4_bbr',
                                                    'struct_brain_mask']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['struct_2_MNI_warp',
                                                     'epi_2_struct_mat',
                                                     'struct_2_epi_mat',
                                                     'epi_2_MNI_warp',
                                                     'MNI_2_epi_warp',
                                                     'fs_2_struct_mat',
                                                     'mean_epi_structSpace',
                                                     'mean_epi_MNIspace',
                                                     'struct_MNIspace']),
                      name='outputnode')

    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]




    ##########################################
    # TOC REGISTRATION MATS AND WARPS
    ##########################################
    # I. STRUCT -> MNI
    ## 1. STRUCT -> MNI with FLIRT
    ## 2. CALC. WARP STRUCT -> MNI with FNIRT

    # II.EPI -> STRUCT
    ## 3. calc EPI->STRUCT initial registration
    ## 4. run EPI->STRUCT via bbr
    ## 5. INVERT to get: STRUCT -> EPI

    # III. COMBINE I. & II.: EPI -> MNI
    ## 6. COMBINE MATS: EPI -> MNI
    ## 7. MNI -> EPI


    ##########################################
    # CREATE REGISTRATION MATS AND WARPS
    ##########################################

    # I. STRUCT -> MNI
    ##########################################
    # 1. REGISTER STRUCT -> MNI with FLIRT
    struct_2_MNI_mat = Node(fsl.FLIRT(dof=12), name='struct_2_MNI_mat')
    struct_2_MNI_mat.inputs.reference = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')

    reg_wf.connect(inputnode, 't1w_brain', struct_2_MNI_mat, 'in_file')
    reg_wf.connect(struct_2_MNI_mat, 'out_matrix_file', outputnode, 'struct_2_MNI_mat_flirt')



    # 2. CALC. WARP STRUCT -> MNI with FNIRT
    # cf. wrt. 2mm
    # https://www.jiscmail.ac.uk/cgi-bin/webadmin?A2=ind1311&L=FSL&P=R86108&1=FSL&9=A&J=on&d=No+Match%3BMatch%3BMatches&z=4
    struct_2_MNI_warp = Node(fsl.FNIRT(), name='struct_2_MNI_warp')
    struct_2_MNI_warp.inputs.config_file = 'T1_2_MNI152_2mm'
    struct_2_MNI_warp.inputs.ref_file = fsl.Info.standard_image('MNI152_T1_2mm.nii.gz')
    struct_2_MNI_warp.inputs.field_file = 'struct_2_MNI_warp.nii.gz'
    struct_2_MNI_warp.plugin_args = {'submit_specs': 'request_memory = 4000'}


    reg_wf.connect(inputnode, 't1w', struct_2_MNI_warp, 'in_file')
    reg_wf.connect(struct_2_MNI_mat, 'out_matrix_file', struct_2_MNI_warp, 'affine_file')
    reg_wf.connect(struct_2_MNI_warp, 'field_file', ds, 'registration.struct_2_MNI_warp')
    reg_wf.connect(struct_2_MNI_warp, 'field_file', outputnode, 'struct_2_MNI_warp')
    reg_wf.connect(struct_2_MNI_warp, 'warped_file', outputnode, 'struct_MNIspace')
    reg_wf.connect(struct_2_MNI_warp, 'warped_file', ds, 'registration.struct_MNIspace')


    # II.EPI -> STRUCT (via bbr)
    ##########################################

    # 3. calc EPI->STRUCT initial registration with flirt dof=6 and corratio
    epi_2_struct_flirt6_mat = Node(fsl.FLIRT(dof=6, cost='corratio'), name='epi_2_struct_flirt6_mat')
    epi_2_struct_flirt6_mat.inputs.out_file = 'epi_structSpace_flirt6.nii.gz'
    reg_wf.connect(inputnode, 't1w_brain', epi_2_struct_flirt6_mat, 'reference')
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', epi_2_struct_flirt6_mat, 'in_file')

    # 4. run EPI->STRUCT via bbr
    bbr_shedule = os.path.join(os.getenv('FSLDIR'), 'etc/flirtsch/bbr.sch')
    epi_2_struct_bbr_mat = Node(interface=fsl.FLIRT(dof=6, cost='bbr'), name='epi_2_struct_bbr_mat')
    epi_2_struct_bbr_mat.inputs.schedule = bbr_shedule
    epi_2_struct_bbr_mat.inputs.out_file = 'epi_structSpace.nii.gz'
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', epi_2_struct_bbr_mat, 'in_file')
    reg_wf.connect(inputnode, 't1w_brain', epi_2_struct_bbr_mat, 'reference')
    reg_wf.connect(epi_2_struct_flirt6_mat, 'out_matrix_file', epi_2_struct_bbr_mat, 'in_matrix_file')
    reg_wf.connect(inputnode, 'wm_mask_4_bbr', epi_2_struct_bbr_mat, 'wm_seg')
    reg_wf.connect(epi_2_struct_bbr_mat, 'out_matrix_file', ds, 'registration.epi_2_struct_mat')
    reg_wf.connect(epi_2_struct_bbr_mat, 'out_file', outputnode, 'mean_epi_structSpace')


    # 5. INVERT to get: STRUCT -> EPI
    struct_2_epi_mat = Node(fsl.ConvertXFM(invert_xfm=True), name='struct_2_epi_mat')
    reg_wf.connect(epi_2_struct_bbr_mat, 'out_matrix_file', struct_2_epi_mat, 'in_file')
    reg_wf.connect(struct_2_epi_mat, 'out_file', outputnode, 'struct_2_epi_mat')


    # III. COMBINE I. & II.: EPI -> MNI
    ##########################################
    # 6. COMBINE MATS: EPI -> MNI
    epi_2_MNI_warp = Node(fsl.ConvertWarp(), name='epi_2_MNI_warp')
    epi_2_MNI_warp.inputs.reference = fsl.Info.standard_image('MNI152_T1_2mm.nii.gz')
    reg_wf.connect(epi_2_struct_bbr_mat, 'out_matrix_file', epi_2_MNI_warp, 'premat')  # epi2struct
    reg_wf.connect(struct_2_MNI_warp, 'field_file', epi_2_MNI_warp, 'warp1')  # struct2mni
    reg_wf.connect(epi_2_MNI_warp, 'out_file', outputnode, 'epi_2_MNI_warp')
    reg_wf.connect(epi_2_MNI_warp, 'out_file', ds, 'registration.epi_2_MNI_warp')


    # output: out_file

    # 7. MNI -> EPI
    MNI_2_epi_warp = Node(fsl.InvWarp(), name='MNI_2_epi_warp')
    MNI_2_epi_warp.inputs.reference = fsl.Info.standard_image('MNI152_T1_2mm.nii.gz')
    reg_wf.connect(epi_2_MNI_warp, 'out_file', MNI_2_epi_warp, 'warp')
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', MNI_2_epi_warp, 'reference')
    reg_wf.connect(MNI_2_epi_warp, 'inverse_warp', outputnode, 'MNI_2_epi_warp')
    # output: inverse_warp




    ##########################################
    # TRANSFORM VOLUMES
    ##########################################

    # CREATE STRUCT IN EPI SPACE FOR DEBUGGING
    struct_epiSpace = Node(fsl.ApplyXfm(), name='struct_epiSpace')
    struct_epiSpace.inputs.out_file = 'struct_brain_epiSpace.nii.gz'
    reg_wf.connect(inputnode, 't1w_brain', struct_epiSpace, 'in_file')
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', struct_epiSpace, 'reference')
    reg_wf.connect(struct_2_epi_mat, 'out_file', struct_epiSpace, 'in_matrix_file')
    reg_wf.connect(struct_epiSpace, 'out_file', ds, 'QC.struct_brain_epiSpace')

    # CREATE EPI IN MNI SPACE
    mean_epi_MNIspace = Node(fsl.ApplyWarp(), name='mean_epi_MNIspace')
    mean_epi_MNIspace.inputs.ref_file = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    mean_epi_MNIspace.inputs.out_file = 'mean_epi_MNIspace.nii.gz'
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', mean_epi_MNIspace, 'in_file')
    reg_wf.connect(epi_2_MNI_warp, 'out_file', mean_epi_MNIspace, 'field_file')
    reg_wf.connect(mean_epi_MNIspace, 'out_file', ds, 'registration.mean_epi_MNIspace')
    reg_wf.connect(mean_epi_MNIspace, 'out_file', outputnode, 'mean_epi_MNIspace')



    # CREATE MNI IN EPI SPACE FOR DEBUGGING
    MNI_epiSpace = Node(fsl.ApplyWarp(), name='MNI_epiSpace')
    MNI_epiSpace.inputs.in_file = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    MNI_epiSpace.inputs.out_file = 'MNI_epiSpace.nii.gz'
    reg_wf.connect(inputnode, 'initial_mean_epi_moco', MNI_epiSpace, 'ref_file')
    reg_wf.connect(MNI_2_epi_warp, 'inverse_warp', MNI_epiSpace, 'field_file')
    reg_wf.connect(MNI_epiSpace, 'out_file', ds, 'registration.MNI_epiSpace')



    reg_wf.write_graph(dotfilename=reg_wf.name, graph2use='flat', format='pdf')

    return reg_wf
