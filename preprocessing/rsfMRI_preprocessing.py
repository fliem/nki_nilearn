__author__ = 'franzliem'

import os

from nipype.pipeline.engine import Node, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl

from preprocessing.moco import create_moco_pipeline
from denoise import create_denoise_pipeline
from struct_preprocessing import create_struct_preproc_pipeline
from registration import create_registration_pipeline
from deskull import create_deskull_pipeline
from qc import create_qc_pipeline


def create_rsfMRI_preproc_pipeline(working_dir, freesurfer_dir, ds_dir, use_fs_brainmask, name='rsfMRI_preprocessing'):
    # initiate workflow
    rsfMRI_preproc_wf = Workflow(name=name)
    rsfMRI_preproc_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting')
    ds_dir = os.path.join(ds_dir, name)

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # inputnode
    inputnode = Node(util.IdentityInterface(fields=['epi',
                                                    't1w',
                                                    'subject_id',
                                                    'TR_ms',
                                                    'vols_to_drop',
                                                    'lat_ventricle_mask_MNI',
                                                    'lp_cutoff_freq',
                                                    'hp_cutoff_freq']),
                     name='inputnode')

    # outputnode
    outputnode = Node(util.IdentityInterface(fields=['epi_moco',
                                                     'rs_preprocessed',
                                                     'epi_2_MNI_warp']),
                      name='outputnode')


    # MOCO
    moco = create_moco_pipeline(working_dir, ds_dir, 'motion_correction')
    rsfMRI_preproc_wf.connect(inputnode, 'epi', moco, 'inputnode.epi')
    rsfMRI_preproc_wf.connect(inputnode, 'vols_to_drop', moco, 'inputnode.vols_to_drop')



    # STRUCT PREPROCESSING
    struct_preproc = create_struct_preproc_pipeline(working_dir, freesurfer_dir, ds_dir, use_fs_brainmask, 'struct_preproc')
    rsfMRI_preproc_wf.connect(inputnode, 't1w', struct_preproc, 'inputnode.t1w')
    rsfMRI_preproc_wf.connect(inputnode, 'subject_id', struct_preproc, 'inputnode.subject_id')



    # REGISTRATIONS
    reg = create_registration_pipeline(working_dir, freesurfer_dir, ds_dir, 'registration')
    rsfMRI_preproc_wf.connect(moco, 'outputnode.initial_mean_epi_moco', reg, 'inputnode.initial_mean_epi_moco')
    rsfMRI_preproc_wf.connect(inputnode, 't1w', reg, 'inputnode.t1w')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.t1w_brain', reg, 'inputnode.t1w_brain')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.wm_mask_4_bbr', reg, 'inputnode.wm_mask_4_bbr')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.struct_brain_mask', reg, 'inputnode.struct_brain_mask')
    rsfMRI_preproc_wf.connect(inputnode, 'subject_id', reg, 'inputnode.subject_id')
    rsfMRI_preproc_wf.connect(reg, 'outputnode.epi_2_MNI_warp', outputnode, 'epi_2_MNI_warp')



    # DESKULL EPI
    deskull = create_deskull_pipeline(working_dir, ds_dir, 'deskull')
    rsfMRI_preproc_wf.connect(moco, 'outputnode.epi_moco', deskull, 'inputnode.epi_moco')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.struct_brain_mask', deskull, 'inputnode.struct_brain_mask')
    rsfMRI_preproc_wf.connect(reg, 'outputnode.struct_2_epi_mat', deskull, 'inputnode.struct_2_epi_mat')




    # DENOISE
    denoise = create_denoise_pipeline(working_dir, ds_dir, 'denoise')
    rsfMRI_preproc_wf.connect(inputnode, 'TR_ms', denoise, 'inputnode.TR_ms')
    rsfMRI_preproc_wf.connect(inputnode, 'subject_id', denoise, 'inputnode.subject_id')
    rsfMRI_preproc_wf.connect(inputnode, 'lat_ventricle_mask_MNI', denoise, 'inputnode.lat_ventricle_mask_MNI')
    rsfMRI_preproc_wf.connect(moco, 'outputnode.par_moco', denoise, 'inputnode.par_moco')
    rsfMRI_preproc_wf.connect(deskull, 'outputnode.epi_deskulled', denoise, 'inputnode.epi')
    rsfMRI_preproc_wf.connect(deskull, 'outputnode.mean_epi', denoise, 'inputnode.mean_epi')
    rsfMRI_preproc_wf.connect(deskull, 'outputnode.brain_mask_epiSpace', denoise, 'inputnode.brain_mask_epiSpace')
    rsfMRI_preproc_wf.connect(reg, 'outputnode.struct_2_epi_mat', denoise, 'inputnode.struct_2_epi_mat')
    rsfMRI_preproc_wf.connect(reg, 'outputnode.MNI_2_epi_warp', denoise, 'inputnode.MNI_2_epi_warp')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.wm_mask', denoise, 'inputnode.wm_mask')
    rsfMRI_preproc_wf.connect(struct_preproc, 'outputnode.csf_mask', denoise, 'inputnode.csf_mask')
    rsfMRI_preproc_wf.connect(inputnode, 'lp_cutoff_freq', denoise, 'inputnode.lp_cutoff_freq')
    rsfMRI_preproc_wf.connect(inputnode, 'hp_cutoff_freq', denoise, 'inputnode.hp_cutoff_freq')

    rsfMRI_preproc_wf.connect(denoise, 'outputnode.rs_preprocessed', outputnode, 'rs_preprocessed')



    # QC
    qc = create_qc_pipeline(working_dir, ds_dir, 'qc')
    rsfMRI_preproc_wf.connect(inputnode, 'subject_id', qc, 'inputnode.subject_id')
    rsfMRI_preproc_wf.connect(moco, 'outputnode.par_moco', qc, 'inputnode.par_moco')
    rsfMRI_preproc_wf.connect(deskull, 'outputnode.epi_deskulled', qc, 'inputnode.epi_deskulled')
    rsfMRI_preproc_wf.connect(deskull, 'outputnode.brain_mask_epiSpace', qc, 'inputnode.brain_mask_epiSpace')
    rsfMRI_preproc_wf.connect([(struct_preproc, qc, [('outputnode.t1w_brain', 'inputnode.t1w_brain'),
                                                     ('outputnode.struct_brain_mask', 'inputnode.struct_brain_mask')])])
    rsfMRI_preproc_wf.connect([(reg, qc, [('outputnode.mean_epi_structSpace', 'inputnode.mean_epi_structSpace'),
                                          ('outputnode.mean_epi_MNIspace', 'inputnode.mean_epi_MNIspace'),
                                          ('outputnode.struct_MNIspace', 'inputnode.struct_MNIspace'),
                                          ('outputnode.struct_2_MNI_warp', 'inputnode.struct_2_MNI_warp')])])
    rsfMRI_preproc_wf.connect(denoise, 'outputnode.outlier_files', qc, 'inputnode.outlier_files')
    rsfMRI_preproc_wf.connect(denoise, 'outputnode.rs_preprocessed', qc, 'inputnode.rs_preprocessed')

    rsfMRI_preproc_wf.write_graph(dotfilename=rsfMRI_preproc_wf.name, graph2use='orig', format='pdf')
    rsfMRI_preproc_wf.write_graph(dotfilename=rsfMRI_preproc_wf.name, graph2use='colored', format='pdf')

    return rsfMRI_preproc_wf

