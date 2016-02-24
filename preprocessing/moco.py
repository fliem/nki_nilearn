from nipype.pipeline.engine import MapNode, Node, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
import nipype.interfaces.io as nio
import os

from cpac_0391_local.generate_motion_statistics import calculate_FD_P
from preprocessing.utils import calculate_mean_FD_fct

def strip_rois_func(in_file, t_min):
    '''
    Removing intial volumes from a time series
    '''
    import numpy as np
    import nibabel as nb
    import os
    from nipype.utils.filemanip import split_filename
    nii = nb.load(in_file)
    new_nii = nb.Nifti1Image(nii.get_data()[:,:,:,t_min:], nii.get_affine(), nii.get_header())
    new_nii.set_data_dtype(np.float32)
    _, base, _ = split_filename(in_file)
    nb.save(new_nii, base + "_roi.nii.gz")
    return os.path.abspath(base + "_roi.nii.gz")



def create_moco_pipeline(working_dir, ds_dir, name='motion_correction'):
    """
    Workflow for motion correction to 1st volume
    based on https://github.com/NeuroanatomyAndConnectivity/pipelines/blob/master/src/lsd_lemon/func_preproc/moco.py
    """

    # initiate workflow
    moco_wf = Workflow(name=name)
    moco_wf.base_dir = os.path.join(working_dir,'LeiCA_resting', 'rsfMRI_preprocessing')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # I/O NODES
    inputnode = Node(util.IdentityInterface(fields=['epi',
                                                    'vols_to_drop']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['epi_moco',
                                                     'par_moco',
                                                     'mat_moco',
                                                     'rms_moco',
                                                     'initial_mean_epi_moco',
                                                     'rotplot',
                                                     'transplot',
                                                     'dispplots',
                                                     'tsnr_file',
                                                     'epi_mask']),
                      name='outputnode')

    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]



    # REMOVE FIRST VOLUMES
    drop_vols = Node(util.Function(input_names=['in_file','t_min'],
                                    output_names=['out_file'],
                                    function=strip_rois_func),
                     name='remove_vol')

    moco_wf.connect(inputnode, 'epi', drop_vols, 'in_file')
    moco_wf.connect(inputnode, 'vols_to_drop', drop_vols, 't_min')


    # MCFILRT MOCO TO 1st VOLUME
    mcflirt = Node(fsl.MCFLIRT(save_mats=True,
                               save_plots=True,
                               save_rms=True,
                               ref_vol=0,
                               out_file='rest_realigned.nii.gz'
                               ),
                   name='mcflirt')

    moco_wf.connect(drop_vols, 'out_file', mcflirt, 'in_file')
    moco_wf.connect([(mcflirt, ds, [('par_file', 'realign.par.@par'),
                                    ('mat_file', 'realign.MAT.@mat'),
                                    ('rms_files', 'realign.plots.@rms')])])
    moco_wf.connect([(mcflirt, outputnode, [('out_file', 'epi_moco'),
                                            ('par_file', 'par_moco'),
                                            ('mat_file', 'mat_moco'),
                                            ('rms_files', 'rms_moco')])])



    # CREATE MEAN EPI (INTENSITY NORMALIZED)
    initial_mean_epi_moco = Node(fsl.maths.MeanImage(dimension='T',
                                             out_file='initial_mean_epi_moco.nii.gz'),
                         name='initial_mean_epi_moco')
    moco_wf.connect(mcflirt, 'out_file', initial_mean_epi_moco, 'in_file')
    moco_wf.connect(initial_mean_epi_moco, 'out_file', outputnode, 'initial_mean_epi_moco')
    moco_wf.connect(initial_mean_epi_moco, 'out_file', ds, 'QC.initial_mean_epi_moco')




    # PLOT MOTION PARAMETERS
    rotplotter = Node(fsl.PlotMotionParams(in_source='fsl',
                                           plot_type='rotations',
                                           out_file='rotation_plot.png'),
                      name='rotplotter')

    moco_wf.connect(mcflirt, 'par_file', rotplotter, 'in_file')
    moco_wf.connect(rotplotter, 'out_file', ds, 'realign.plots.@rotplot')



    transplotter = Node(fsl.PlotMotionParams(in_source='fsl',
                                             plot_type='translations',
                                             out_file='translation_plot.png'),
                        name='transplotter')

    moco_wf.connect(mcflirt, 'par_file', transplotter, 'in_file')
    moco_wf.connect(transplotter, 'out_file', ds, 'realign.plots.@transplot')



    dispplotter = MapNode(interface=fsl.PlotMotionParams(in_source='fsl',
                                                         plot_type='displacement'),
                          name='dispplotter',
                          iterfield=['in_file'])
    dispplotter.iterables = ('plot_type', ['displacement'])

    moco_wf.connect(mcflirt, 'rms_files', dispplotter, 'in_file')
    moco_wf.connect(dispplotter, 'out_file', ds, 'realign.plots.@dispplots')



    moco_wf.write_graph(dotfilename=moco_wf.name, graph2use='flat', format='pdf')

    return moco_wf
