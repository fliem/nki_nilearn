from nipype.pipeline.engine import Node, MapNode, Workflow
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
import nipype.interfaces.fsl as fsl
from nipype.interfaces.freesurfer.utils import ImageInfo
from nipype.interfaces.dcmstack import DcmStack
from nipype.interfaces.dcm2nii import Dcm2nii
import os


def create_converter_structural_pipeline(working_dir, ds_dir, name='converter_struct'):
    # initiate workflow
    converter_wf = Workflow(name=name)
    converter_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # inputnode
    inputnode = Node(util.IdentityInterface(fields=['t1w_dicom']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['t1w']),
                      name='outputnode')

    niftisink = Node(nio.DataSink(), name='niftisink')
    niftisink.inputs.base_directory = os.path.join(ds_dir, 'raw_niftis')



    # convert to nifti
    # todo check if geometry bugs attac. use dcm2nii?
    converter_t1w = Node(DcmStack(embed_meta=True), name='converter_t1w')
    converter_t1w.plugin_args = {'submit_specs': 'request_memory = 2000'}
    converter_t1w.inputs.out_format = 't1w'

    converter_wf.connect(inputnode, 't1w_dicom', converter_t1w, 'dicom_files')

    # reorient to standard orientation
    reor_2_std = Node(fsl.Reorient2Std(), name='reor_2_std')
    converter_wf.connect(converter_t1w, 'out_file', reor_2_std, 'in_file')

    converter_wf.connect(reor_2_std, 'out_file', outputnode, 't1w')


    # save original niftis
    converter_wf.connect(reor_2_std, 'out_file', niftisink, 'sMRI')


    converter_wf.write_graph(dotfilename='converter_struct', graph2use='flat', format='pdf')
    return converter_wf




def create_converter_diffusion_pipeline(working_dir, ds_dir, name='converter_diffusion'):
    # initiate workflow
    converter_wf = Workflow(name=name)
    converter_wf.base_dir = os.path.join(working_dir, 'LeiCA_resting')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # inputnode
    inputnode = Node(util.IdentityInterface(fields=['dMRI_dicom']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['dMRI']),
                      name='outputnode')

    niftisink = Node(nio.DataSink(), name='niftisink')
    niftisink.inputs.base_directory = os.path.join(ds_dir, 'raw_niftis')

#######

    converter_dMRI = Node(Dcm2nii(), name="converter_dMRI")
    converter_dMRI.inputs.gzip_output = True
    converter_dMRI.inputs.nii_output = True
    converter_dMRI.inputs.anonymize = False
    converter_dMRI.plugin_args={'submit_specs': 'request_memory = 2000'}
    converter_wf.connect(inputnode, 'dMRI_dicom', converter_dMRI, 'source_names')


    dMRI_rename = Node(util.Rename(format_string='DTI_mx_137.nii.gz'), name='dMRI_rename')
    converter_wf.connect(converter_dMRI, 'converted_files', dMRI_rename, 'in_file')


    bvecs_rename = Node(util.Rename(format_string='DTI_mx_137.bvecs'), name='bvecs_rename')
    converter_wf.connect(converter_dMRI, 'bvecs', bvecs_rename, 'in_file')

    bvals_rename = Node(util.Rename(format_string='DTI_mx_137.bvals'), name='bvals_rename')
    converter_wf.connect(converter_dMRI, "bvals", bvals_rename, 'in_file')

    # reorient to standard orientation
    reor_2_std = Node(fsl.Reorient2Std(), name='reor_2_std')
    converter_wf.connect(dMRI_rename, 'out_file', reor_2_std, 'in_file')
    converter_wf.connect(reor_2_std, 'out_file', outputnode, 'dMRI')

    # save original niftis
    converter_wf.connect(reor_2_std, 'out_file', niftisink, 'dMRI.@dwi')
    converter_wf.connect(bvals_rename, 'out_file', niftisink, 'dMRI.@bvals')
    converter_wf.connect(bvecs_rename, 'out_file', niftisink, 'dMRI.@bvecs')


    converter_wf.write_graph(dotfilename='converter_struct', graph2use='flat', format='pdf')
    return converter_wf




def create_converter_functional_pipeline(working_dir, ds_dir, name='converter_funct'):
    # initiate workflow
    converter_wf = Workflow(name=name)
    converter_wf.base_dir = os.path.join(working_dir,'LeiCA_resting')

    # set fsl output
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

    # I/O NODE
    inputnode = Node(util.IdentityInterface(fields=['epi_dicom',
                                                    'out_format']),
                     name='inputnode')

    outputnode = Node(util.IdentityInterface(fields=['epi',
                                                     'TR_ms']),
                      name='outputnode')

    niftisink = Node(nio.DataSink(), name='niftisink')
    niftisink.inputs.base_directory = os.path.join(ds_dir, 'raw_niftis')
    niftisink.inputs.substitutions = [('_TR_id_', 'TR_')]


    # convert to nifti
    # todo check if geometry bugs attac. use dcm2nii?
    converter_epi = Node(DcmStack(embed_meta=True), name='converter_epi')
    converter_epi.plugin_args = {'submit_specs': 'request_memory = 2000'}

    def reformat_filename_fct(TR_str):
        return 'rsfMRI_'+TR_str
    reformat_filename = Node(util.Function(input_names=['TR_str'],
                                           output_names=['filename'],
                                           function=reformat_filename_fct),
                             name='reformat_filename')

    converter_wf.connect(inputnode, 'out_format', reformat_filename, 'TR_str')
    converter_wf.connect(inputnode, 'epi_dicom', converter_epi, 'dicom_files')
    converter_wf.connect(reformat_filename, 'filename', converter_epi, 'out_format')

    # reorient to standard orientation
    reor_2_std = Node(fsl.Reorient2Std(), name='reor_2_std')
    converter_wf.connect(converter_epi, 'out_file', reor_2_std, 'in_file')

    converter_wf.connect(reor_2_std, 'out_file', outputnode, 'epi')


    # save original niftis
    converter_wf.connect(reor_2_std, 'out_file', niftisink, 'rsfMRI')


    # GET TR FROM .nii
    def check_TR_fct(TR):
        print ' '
        print 'check_TR_fct checks validity of TR'
        print('imported TR is %s' % TR)
        print '  '
        try:
            float(TR)
        except ValueError:
            isvalid_TR = 0
            raise Exception('ERROR: TR COULD NOT AUTOMATICALLY BE EXTRACTED FROM EPI.\nEXECUTION STOPPED')
        else:
            isvalid_TR = 1
            print 'TR is valid'
        if isvalid_TR:
            if float(TR <= 0):
                raise Exception('ERROR: TR NOT VALID (<=0).\nEXECUTION STOPPED')
        return float(TR)

    get_TR = Node(ImageInfo(), name='get_TR')
    converter_wf.connect(reor_2_std, 'out_file', get_TR, 'in_file')

    check_TR = Node(util.Function(input_names=['TR'],
                                  output_names=['TR_ms'], function=check_TR_fct), name='check_TR')

    converter_wf.connect(get_TR, 'TR', check_TR, 'TR')
    converter_wf.connect(check_TR, 'TR_ms', outputnode, 'TR_ms')



    converter_wf.write_graph(dotfilename=converter_wf.name, graph2use='flat', format='pdf')

    return converter_wf

