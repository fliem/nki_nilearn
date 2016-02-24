import os

from nipype.pipeline.engine import Node, Workflow
import nipype.interfaces.fsl as fsl
import nipype.interfaces.utility as util
from nipype.algorithms import rapidart
import nipype.interfaces.io as nio



import cpac_0391_local.generate_motion_statistics as cpac_generate_motion_statistics
import cpac_0391_local.nuisance as cpac_nuisance

from preprocessing.utils import extract_signal_from_tissue, time_normalizer



'''
Main workflow for denoising
Based on: based on https://github.com/NeuroanatomyAndConnectivity/pipelines/blob/master/src/lsd_lemon/func_preproc/denoise.py

Largely based on https://github.com/nipy/nipype/blob/master/examples/
rsfmri_vol_surface_preprocessing_nipy.py#L261
but denoising in anatomical space
'''


def create_denoise_pipeline(working_dir, ds_dir, name='denoise'):
    # workflow
    denoise_wf = Workflow(name=name)
    denoise_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting', 'rsfMRI_preprocessing')

    # I/O NODES
    inputnode = Node(interface=util.IdentityInterface(fields=['subject_id',
                                                              'epi',
                                                              'mean_epi',
                                                              'par_moco',
                                                              'struct_2_epi_mat',
                                                              'MNI_2_epi_warp',
                                                              'lat_ventricle_mask_MNI',
                                                              'wm_mask',
                                                              'csf_mask',
                                                              'brain_mask_epiSpace',
                                                              'TR_ms',
                                                              'lp_cutoff_freq',
                                                              'hp_cutoff_freq']),
                     name='inputnode')

    outputnode = Node(interface=util.IdentityInterface(fields=['outlier_files',
                                                               'rs_preprocessed']),
                      name='outputnode')

    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]


    ######### TRANSFORM MASKS



    wm_mask_epiSpace = Node(fsl.ApplyXfm(apply_xfm=True, interp='nearestneighbour'), name='wm_mask_epiSpace')
    wm_mask_epiSpace.inputs.out_file = 'wm_mask_epiSpace.nii.gz'
    denoise_wf.connect([(inputnode, wm_mask_epiSpace, [('wm_mask', 'in_file'),
                                                       ('mean_epi', 'reference'),
                                                       ('struct_2_epi_mat', 'in_matrix_file')])])

    denoise_wf.connect(wm_mask_epiSpace, 'out_file', ds, 'masks.wm_mask_epiSpace')

    csf_mask_epiSpace = Node(fsl.ApplyXfm(apply_xfm=True, interp='nearestneighbour'), name='csf_mask_epiSpace')
    denoise_wf.connect([(inputnode, csf_mask_epiSpace, [('csf_mask', 'in_file'),
                                                       ('mean_epi', 'reference'),
                                                       ('struct_2_epi_mat', 'in_matrix_file')])])



     # MOVE LATERAL VENTRICLE MASK INTO EPI SPACE
    lat_ventricle_mask_epiSpace = Node(fsl.ApplyWarp(interp='nn'), name='lat_ventricle_mask_epiSpace')
    denoise_wf.connect(inputnode, 'lat_ventricle_mask_MNI', lat_ventricle_mask_epiSpace, 'in_file')
    denoise_wf.connect(inputnode, 'mean_epi', lat_ventricle_mask_epiSpace, 'ref_file')
    denoise_wf.connect(inputnode, 'MNI_2_epi_warp', lat_ventricle_mask_epiSpace, 'field_file')

    # CONFINE INDIVIDUAL CSF MASK TO LATERAL VENTRICLES
    csf_mask_lat_ventricles_epiSpace = Node(fsl.maths.BinaryMaths(operation='mul'),
                                            name='csf_mask_lat_ventricles_epiSpace')
    csf_mask_lat_ventricles_epiSpace.inputs.out_file = 'csf_mask_epiSpace.nii.gz'
    denoise_wf.connect(csf_mask_epiSpace, 'out_file', csf_mask_lat_ventricles_epiSpace, 'in_file')
    denoise_wf.connect(lat_ventricle_mask_epiSpace, 'out_file', csf_mask_lat_ventricles_epiSpace, 'operand_file')
    denoise_wf.connect(csf_mask_lat_ventricles_epiSpace, 'out_file', ds, 'masks.csf_mask_lat_ventr_epiSpace')




    # TR CONVERSION
    def get_TR_in_sec_fct(TR_ms):
        return TR_ms / 1000.0

    get_TR_in_sec = Node(util.Function(input_names=['TR_ms'],
                                       output_names=['TR_sec'],
                                       function=get_TR_in_sec_fct),
                         name='get_TR_in_sec')

    denoise_wf.connect(inputnode, 'TR_ms', get_TR_in_sec, 'TR_ms')


    # RUN ARTIFACT DETECTION
    artifact = Node(rapidart.ArtifactDetect(save_plot=True,
                                            use_norm=True,
                                            parameter_source='FSL',
                                            mask_type='file',
                                            norm_threshold=1,
                                            zintensity_threshold=3,
                                            use_differences=[True, False]
                                            ),
                    name='artifact')
    artifact.plugin_args = {'submit_specs': 'request_memory = 17000'}

    denoise_wf.connect(inputnode, 'epi', artifact, 'realigned_files')
    denoise_wf.connect([(inputnode, artifact, [('par_moco', 'realignment_parameters')])])
    denoise_wf.connect(inputnode, 'brain_mask_epiSpace', artifact, 'mask_file')


    denoise_wf.connect([(artifact, ds, [('norm_files', 'denoise.artefact.@combined_motion'),
                                        ('outlier_files', 'denoise.artefact.@outlier'),
                                        ('intensity_files', 'denoise.artefact.@intensity'),
                                        ('statistic_files', 'denoise.artefact.@outlierstats'),
                                        ('plot_files', 'denoise.artefact.@outlierplots')])])
    denoise_wf.connect(artifact, 'outlier_files', outputnode, 'outlier_files')
    ############################


    def combine_motion_parameters_with_outliers_fct(motion_params, outliers_file, spike_reg):
        """Adapted from rom https://github.com/nipy/nipype/blob/master/examples/
        rsfmri_vol_surface_preprocessing_nipy.py#L261
        """

        import numpy as np
        import os
        if spike_reg:
            out_params = np.genfromtxt(motion_params)
            try:
                outlier_val = np.genfromtxt(outliers_file)
            except IOError:
                outlier_val = np.empty((0))
            for index in np.atleast_1d(outlier_val):
                outlier_vector = np.zeros((out_params.shape[0], 1))
                outlier_vector[index] = 1
                out_params = np.hstack((out_params, outlier_vector))

            out_file = os.path.join(os.getcwd(), "motion_outlier_regressor.txt") #"filter_regressor%02d.txt" % idx)
            np.savetxt(out_file, out_params, fmt="%.8f")
        else:
            out_file=motion_params

        return out_file
    ############################


    # COMPUTE MOTION DERIVATIVES (FRISTON24)
    friston24 = Node(util.Function(input_names=['in_file'],
                                   output_names=['friston_par'],
                                   function=cpac_generate_motion_statistics.calc_friston_twenty_four),
                     name='friston24')
    denoise_wf.connect(inputnode, 'par_moco', friston24, 'in_file')


    # CREATE OUTLIER DUMMY REGRESSOR AND COMBINE WITH FRISTON24
    motion_and_outlier_regressor = Node(util.Function(input_names=['motion_params', 'outliers_file', 'spike_reg'],
                                                      output_names=['out_file'],
                                                      function=combine_motion_parameters_with_outliers_fct),
                                        name='motion_and_outlier_regressor')
    motion_and_outlier_regressor.inputs.spike_reg = True
    denoise_wf.connect(friston24, 'friston_par', motion_and_outlier_regressor, 'motion_params')
    denoise_wf.connect(artifact, 'outlier_files', motion_and_outlier_regressor, 'outliers_file')

    # EXTRACT SIGNAL FROM WM AND CSF FOR COMPCOR
    wm_sig = Node(util.Function(input_names=['data_file', 'mask_file'],
                                output_names=['out_file'],
                                function=extract_signal_from_tissue),
                  name='wm_sig')

    denoise_wf.connect(inputnode, 'epi', wm_sig, 'data_file')
    denoise_wf.connect(wm_mask_epiSpace, 'out_file', wm_sig, 'mask_file')

    csf_sig = Node(util.Function(input_names=['data_file', 'mask_file'],
                                 output_names=['out_file'],
                                 function=extract_signal_from_tissue),
                   name='csf_sig')

    denoise_wf.connect(inputnode, 'epi', csf_sig, 'data_file')
    denoise_wf.connect(csf_mask_lat_ventricles_epiSpace, 'out_file', csf_sig, 'mask_file')


    nuisance_selector = {'compcor': True,
                             'wm': False,
                             'csf': False,
                             'gm': False,
                             'global': False,
                             'pc1': False,
                             'motion': True,
                             'linear': True,
                             'quadratic': True}



    nuisance_reg = Node(util.Function(input_names=['subject',
                                                   'selector',
                                                   'wm_sig_file',
                                                   'csf_sig_file',
                                                   'gm_sig_file',
                                                   'motion_file',
                                                   'compcor_ncomponents'],
                                      output_names=['residual_file', 'regressors_file'],
                                      function=cpac_nuisance.calc_residuals),
                        name='nuisance_reg')

    nuisance_reg.inputs.compcor_ncomponents = 5
    nuisance_reg.inputs.selector = nuisance_selector
    denoise_wf.connect(inputnode, 'epi', nuisance_reg, 'subject')
    denoise_wf.connect(wm_sig, 'out_file', nuisance_reg, 'wm_sig_file')
    denoise_wf.connect(csf_sig, 'out_file', nuisance_reg, 'csf_sig_file')
    denoise_wf.connect(motion_and_outlier_regressor, 'out_file', nuisance_reg, 'motion_file')
    denoise_wf.connect(nuisance_reg, 'regressors_file', ds, 'denoise.regression.regressor')
    denoise_wf.connect(nuisance_reg, 'residual_file', ds, 'epis.01_denoised')

    ############################



    # BANDPASS FILTER
    # sigma calculation see
    # https://www.jiscmail.ac.uk/cgi-bin/webadmin?A2=ind1205&L=FSL&P=R57592&1=FSL&9=A&I=-3&J=on&d=No+Match%3BMatch%3BMatches&z=4
    def calc_bp_sigma_fct(TR_sec, cutoff_freq):
        sigma = 1. / (2 * TR_sec * cutoff_freq)
        return sigma


    calc_lp_sigma = Node(util.Function(input_names=['TR_sec', 'cutoff_freq'],
                                       output_names=['sigma'],
                                       function=calc_bp_sigma_fct), name='calc_lp_sigma')
    denoise_wf.connect(get_TR_in_sec, 'TR_sec', calc_lp_sigma, 'TR_sec')
    denoise_wf.connect(inputnode, 'lp_cutoff_freq', calc_lp_sigma, 'cutoff_freq')

    calc_hp_sigma = Node(util.Function(input_names=['TR_sec', 'cutoff_freq'],
                                       output_names=['sigma'],
                                       function=calc_bp_sigma_fct), name='calc_hp_sigma')
    denoise_wf.connect(get_TR_in_sec, 'TR_sec', calc_hp_sigma, 'TR_sec')
    denoise_wf.connect(inputnode, 'hp_cutoff_freq', calc_hp_sigma, 'cutoff_freq')

    bp_filter = Node(fsl.TemporalFilter(), name='bp_filter')
    bp_filter.plugin_args = {'submit_specs': 'request_memory = 4000'}

    denoise_wf.connect(nuisance_reg, 'residual_file', bp_filter, 'in_file')
    denoise_wf.connect(calc_lp_sigma, 'sigma', bp_filter, 'lowpass_sigma')
    denoise_wf.connect(calc_hp_sigma, 'sigma', bp_filter, 'highpass_sigma')
    denoise_wf.connect(bp_filter, 'out_file', ds, 'epis.02_denoised_BP')



    # TIME-NORMALIZE SCAN
    normalize_time = Node(util.Function(input_names=['in_file', 'tr'],
                                        output_names=['out_file'],
                                        function=time_normalizer),
                          name='normalize_time')
    #fixme req mem needed?
    #normalize_time.plugin_args = {'submit_specs': 'request_memory = 17000'}
    denoise_wf.connect(bp_filter, 'out_file', normalize_time, 'in_file')
    denoise_wf.connect(get_TR_in_sec, 'TR_sec', normalize_time, 'tr')

    denoise_wf.connect(normalize_time, 'out_file', outputnode, 'rs_preprocessed')
    denoise_wf.connect(normalize_time, 'out_file', ds, 'epis.03_denoised_BP_tNorm')

    denoise_wf.write_graph(dotfilename=denoise_wf.name, graph2use='flat', format='pdf')

    return denoise_wf

