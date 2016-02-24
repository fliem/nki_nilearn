from nipype.pipeline.engine import MapNode, Node, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.fsl as fsl
import nipype.interfaces.io as nio
import nipype.algorithms.misc as misc

import os


def create_deskull_pipeline(working_dir, ds_dir, name='deskull'):


    # initiate workflow
    deskull_wf = Workflow(name=name)
    deskull_wf.base_dir = os.path.join(working_dir,'LeiCA_resting', 'rsfMRI_preprocessing')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # I/O NODES
    inputnode = Node(util.IdentityInterface(fields=['epi_moco',
                                                    'struct_brain_mask',
                                                    'struct_2_epi_mat']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['epi_deskulled',
                                                     'mean_epi',
                                                     'brain_mask_epiSpace']),
                      name='outputnode')

    ds = Node(nio.DataSink(base_directory=ds_dir), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]


    # TRANSFORM BRAIN MASK TO EPI SPACE
    brain_mask_epiSpace = Node(fsl.ApplyXfm(apply_xfm=True, interp='nearestneighbour'), name='brain_mask_epiSpace')
    brain_mask_epiSpace.inputs.out_file = 'brain_mask_epiSpace.nii.gz'
    deskull_wf.connect([(inputnode, brain_mask_epiSpace, [('struct_brain_mask', 'in_file'),
                                                       ('epi_moco', 'reference'),
                                                       ('struct_2_epi_mat', 'in_matrix_file')])])

    deskull_wf.connect(brain_mask_epiSpace, 'out_file', outputnode, 'brain_mask_epiSpace')
    deskull_wf.connect(brain_mask_epiSpace, 'out_file', ds, 'masks.brain_mask_epiSpace')


    # DESKULL EPI
    epi_brain = Node(fsl.maths.BinaryMaths(operation = 'mul'), name='epi_brain')
    deskull_wf.connect(inputnode, 'epi_moco', epi_brain, 'in_file')
    deskull_wf.connect(brain_mask_epiSpace, 'out_file', epi_brain, 'operand_file')



    # GLOBAL INTENSITY NORMALIZATION
    epi_intensity_norm = Node(interface=fsl.ImageMaths(), name='epi_intensity_norm')
    epi_intensity_norm.inputs.op_string = '-ing 10000'
    epi_intensity_norm.out_data_type = 'float'
    deskull_wf.connect(epi_brain, 'out_file', epi_intensity_norm, 'in_file')
    deskull_wf.connect(epi_intensity_norm, 'out_file', outputnode, 'epi_deskulled')


    # CREATE MEAN EPI (INTENSITY NORMALIZED)
    mean_epi = Node(fsl.maths.MeanImage(dimension='T',
                                             out_file='rest_realigned_mean.nii.gz'),
                         name='mean_epi')

    deskull_wf.connect(epi_intensity_norm, 'out_file', mean_epi, 'in_file')
    deskull_wf.connect(mean_epi, 'out_file', ds, 'QC.mean_epi')
    deskull_wf.connect(mean_epi, 'out_file', outputnode, 'mean_epi')




    deskull_wf.write_graph(dotfilename=deskull_wf.name, graph2use='flat', format='pdf')

    return deskull_wf
