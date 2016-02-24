from nipype.pipeline.engine import MapNode, Node, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
import nipype.interfaces.io as nio
import nipype.algorithms.misc as misc
import nipype.interfaces.utility as niu
import pandas as pd
from cpac_0391_local.generate_motion_statistics import calculate_FD_P
from preprocessing.utils import calculate_mean_FD_fct
from nipype.algorithms.metrics import Similarity
from utils import fsl_slices_fct

import os


def create_qc_pipeline(working_dir, ds_dir, name='qc'):
    # initiate workflow
    qc_wf = Workflow(name=name)
    qc_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting', 'rsfMRI_preprocessing')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # I/O NODES
    inputnode = Node(util.IdentityInterface(fields=['subject_id',
                                                    'par_moco',
                                                    'outlier_files',
                                                    'epi_deskulled',
                                                    't1w_brain',
                                                    'mean_epi_structSpace',
                                                    'mean_epi_MNIspace',
                                                    'struct_MNIspace',
                                                    'struct_brain_mask',
                                                    'brain_mask_epiSpace',
                                                    'struct_2_MNI_warp',
                                                    'rs_preprocessed']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['']),
                      name='outputnode')

    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]




    # CALCULATED POWER FD
    FD_power = Node(util.Function(input_names=['in_file'],
                                  output_names=['out_file'],
                                  function=calculate_FD_P),
                    name='FD_power')
    qc_wf.connect(inputnode, 'par_moco', FD_power, 'in_file')
    qc_wf.connect(FD_power, 'out_file', ds, 'QC.FD.FD_ts')

    mean_FD_power = Node(util.Function(input_names=['in_file'],
                                       output_names=['mean_FD_power', 'out_file'],
                                       function=calculate_mean_FD_fct),
                         name='mean_FD_power')
    qc_wf.connect(FD_power, 'out_file', mean_FD_power, 'in_file')
    qc_wf.connect(mean_FD_power, 'out_file', ds, 'QC.FD.FD_mean')



    # EXTRACT NUMBER OF SPIKES (OUTLIERS)
    def get_n_spikes_fct(outliers_file):
        import numpy as np

        try:
            spikes = np.atleast_1d(np.genfromtxt(outliers_file))
        except IOError:
            spikes = np.empty((0))
        n_spikes = len(spikes)
        return n_spikes

    get_n_spikes = Node(util.Function(input_names=['outliers_file'],
                                      output_names=['n_spikes'],
                                      function=get_n_spikes_fct),
                        name='get_n_spikes')
    qc_wf.connect(inputnode, 'outlier_files', get_n_spikes, 'outliers_file')



    # CALCULATE TSNR
    tsnr_uglyname = Node(misc.TSNR(), name='tsnr_uglyname')
    qc_wf.connect(inputnode, 'epi_deskulled', tsnr_uglyname, 'in_file')

    tsnr = Node(niu.Rename(format_string='tsnr', keep_ext=True), name='tsnr')
    qc_wf.connect(tsnr_uglyname, 'tsnr_file', tsnr, 'in_file')
    qc_wf.connect(tsnr, 'out_file', ds, 'QC.tsnr')

    # GET MEAN TSNR IN BRAIN_MASK
    def get_values_inside_a_mask(main_file, mask_file, out_file):
        import nibabel as nb
        import numpy as np
        import os

        out_file = os.path.join(os.getcwd(), out_file + '.npy')
        main_nii = nb.load(main_file)
        main_data = main_nii.get_data()
        nan_mask = np.logical_not(np.isnan(main_data))
        mask = nb.load(mask_file).get_data() > 0

        data = main_data[np.logical_and(nan_mask, mask)]
        np.save(out_file, data)
        median_data = np.median(data)
        return (out_file, median_data)

    get_tsnr = Node(util.Function(input_names=['main_file', 'mask_file', 'out_file'],
                                  output_names=['out_file', 'median_data'],
                                  function=get_values_inside_a_mask),
                    name='get_tsnr')
    get_tsnr.inputs.out_file = 'tsnr'
    qc_wf.connect(tsnr, 'out_file', get_tsnr, 'main_file')
    qc_wf.connect(inputnode, 'brain_mask_epiSpace', get_tsnr, 'mask_file')
    qc_wf.connect(get_tsnr, 'out_file', ds, 'QC.tsnr.@out_file')




    ## CREATE SLICES OVERLAY
    slices_epi_structSpace = Node(util.Function(input_names=['in_file', 'in_file2'], output_names=['out_file'],
                                                function=fsl_slices_fct), name='slices_epi_structSpace')
    qc_wf.connect(inputnode, 'mean_epi_structSpace', slices_epi_structSpace, 'in_file')
    qc_wf.connect(inputnode, 't1w_brain', slices_epi_structSpace, 'in_file2')
    qc_wf.connect(slices_epi_structSpace, 'out_file', ds, 'QC.slices.epi_structSpace')

    slices_epi_MNIspace = Node(util.Function(input_names=['in_file', 'in_file2'], output_names=['out_file'],
                                             function=fsl_slices_fct), name='slices_epi_MNIspace')
    slices_epi_MNIspace.inputs.in_file2 = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    qc_wf.connect(inputnode, 'mean_epi_MNIspace', slices_epi_MNIspace, 'in_file')
    qc_wf.connect(slices_epi_MNIspace, 'out_file', ds, 'QC.slices.epi_MNIspace')

    slices_struct_MNIspace = Node(util.Function(input_names=['in_file', 'in_file2'], output_names=['out_file'],
                                                function=fsl_slices_fct), name='slices_struct_MNIspace')
    qc_wf.connect(inputnode, 'struct_MNIspace', slices_struct_MNIspace, 'in_file')
    slices_struct_MNIspace.inputs.in_file2 = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    qc_wf.connect(slices_struct_MNIspace, 'out_file', ds, 'QC.slices.struct_MNIspace')





    # CREATE BRAIN MASK IN MNI SPACE
    struct_brain_mask_MNIspace = Node(fsl.ApplyWarp(), name='struct_brain_mask_MNIspace', interp='nn')
    struct_brain_mask_MNIspace.inputs.ref_file = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    struct_brain_mask_MNIspace.inputs.out_file = 'struct_brain_mask_MNIspace.nii.gz'
    qc_wf.connect(inputnode, 'struct_brain_mask', struct_brain_mask_MNIspace, 'in_file')
    qc_wf.connect(inputnode, 'struct_2_MNI_warp', struct_brain_mask_MNIspace, 'field_file')


    # CREATE STRUCT_BRAIN IN MNI SPACE
    struct_brain_MNIspace = Node(fsl.ApplyWarp(), name='struct_brain_MNIspace')
    struct_brain_MNIspace.inputs.ref_file = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    struct_brain_MNIspace.inputs.out_file = 'struct_MNIspace.nii.gz'
    qc_wf.connect(inputnode, 't1w_brain', struct_brain_MNIspace, 'in_file')
    qc_wf.connect(inputnode, 'struct_2_MNI_warp', struct_brain_MNIspace, 'field_file')


    def similarity_to_file_fct(similarity):
        import os
        import numpy as np

        out_file = os.path.join(os.getcwd(), 'similarity.txt')
        np.savetxt(out_file, np.array(similarity))
        return out_file


    # CALCULATE SIMILARITY FOR QC
    similarity_epi_struct = Node(interface=Similarity(metric='nmi'),
                                 name='similarity_epi_struct')
    qc_wf.connect(inputnode, 'mean_epi_structSpace', similarity_epi_struct, 'volume1')
    qc_wf.connect(inputnode, 't1w_brain', similarity_epi_struct, 'volume2')
    qc_wf.connect(inputnode, 'struct_brain_mask', similarity_epi_struct, 'mask1')
    qc_wf.connect(inputnode, 'struct_brain_mask', similarity_epi_struct, 'mask2')

    similarity_epi_struct_txt = Node(util.Function(input_names=['similarity'],
                                                   output_names=['out_file'],
                                                   function=similarity_to_file_fct),
                                     name='similarity_epi_struct_txt')
    qc_wf.connect(similarity_epi_struct, 'similarity', similarity_epi_struct_txt, 'similarity')
    qc_wf.connect(similarity_epi_struct_txt, 'out_file', ds, 'QC.similarity.epi_struct')




    similarity_struct_MNI = Node(interface=Similarity(metric='nmi'),
                                 name='similarity_struct_MNI')
    qc_wf.connect(struct_brain_MNIspace, 'out_file', similarity_struct_MNI, 'volume1')
    similarity_struct_MNI.inputs.volume2 = fsl.Info.standard_image('MNI152_T1_2mm_brain.nii.gz')
    qc_wf.connect(struct_brain_mask_MNIspace, 'out_file', similarity_struct_MNI, 'mask1')
    qc_wf.connect(struct_brain_mask_MNIspace, 'out_file', similarity_struct_MNI, 'mask2')

    similarity_struct_MNI_txt = Node(util.Function(input_names=['similarity'],
                                                   output_names=['out_file'],
                                                   function=similarity_to_file_fct),
                                     name='similarity_struct_MNI_txt')
    qc_wf.connect(similarity_struct_MNI, 'similarity', similarity_struct_MNI_txt, 'similarity')
    qc_wf.connect(similarity_struct_MNI_txt, 'out_file', ds, 'QC.similarity.struct_MNI')




    def list_to_num(lst):
        return lst[0]

    def create_qc_df_fct(subject_id, similarity_epi_struct, similarity_struct_MNI, mean_FD_Power, n_spikes,
                         median_tsnr):
        import pandas as pd
        import os

        out_file_df = os.path.join(os.getcwd(), 'qc_values.pkl')
        out_file_txt = os.path.join(os.getcwd(), 'qc_values.txt')
        data = [subject_id, similarity_epi_struct, similarity_struct_MNI, mean_FD_Power, n_spikes, median_tsnr]
        header = ['subject_id', 'similarity_epi_struct', 'similarity_struct_MNI', 'mean_FD_Power', 'n_spikes',
                  'median_tsnr']
        df = pd.DataFrame([data], columns=header)
        df = df.set_index(df.subject_id)
        df.to_pickle(out_file_df)
        df.to_csv(out_file_txt, sep='\t')
        return (out_file_df, out_file_txt)

    create_qc_df = Node(util.Function(input_names=['subject_id',
                                                   'similarity_epi_struct',
                                                   'similarity_struct_MNI',
                                                   'mean_FD_Power',
                                                   'n_spikes',
                                                   'median_tsnr'],
                                      output_names=['out_file_df', 'out_file_txt'],
                                      function=create_qc_df_fct),
                        name='create_qc_df')

    qc_wf.connect(inputnode, 'subject_id', create_qc_df, 'subject_id')
    qc_wf.connect(similarity_epi_struct, ('similarity', list_to_num), create_qc_df, 'similarity_epi_struct')
    qc_wf.connect(similarity_struct_MNI, ('similarity', list_to_num), create_qc_df, 'similarity_struct_MNI')
    qc_wf.connect(mean_FD_power, 'mean_FD_power', create_qc_df, 'mean_FD_Power')
    qc_wf.connect(get_n_spikes, 'n_spikes', create_qc_df, 'n_spikes')
    qc_wf.connect(get_tsnr, 'median_data', create_qc_df, 'median_tsnr')

    qc_wf.connect(create_qc_df, 'out_file_df', ds, 'QC.df.@df')
    qc_wf.connect(create_qc_df, 'out_file_txt', ds, 'QC.df.@txt')

    qc_wf.write_graph(dotfilename=qc_wf.name, graph2use='flat', format='pdf')

    return qc_wf
