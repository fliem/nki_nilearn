
def normalize_epi(subjects_list,
                  TR_list,
                  preprocessed_data_dir,
                  working_dir,
                  ds_dir,
                  template_dir,
                  plugin_name,
                  use_n_procs):

    import os
    from nipype import config
    from nipype.pipeline.engine import Node, Workflow
    import nipype.interfaces.io as nio
    from nipype.interfaces import fsl
    import nipype.interfaces.utility as util


    #####################################
    # GENERAL SETTINGS
    #####################################
    wf = Workflow(name='normalize')
    wf.base_dir = os.path.join(working_dir)

    nipype_cfg = dict(logging=dict(workflow_level='DEBUG'), execution={'stop_on_first_crash': True,
                                                                       'remove_unnecessary_outputs': True,
                                                                       'job_finished_timeout': 120})
    config.update_config(nipype_cfg)
    wf.config['execution']['crashdump_dir'] = os.path.join(working_dir, 'crash')


    ds = Node(nio.DataSink(), name='ds')
    ds.inputs.substitutions = [('_TR_id_', 'TR_')]
    ds.inputs.regexp_substitutions = [('_subject_id_[A0-9]*/', '')]

    #####################################
    # SET ITERATORS
    #####################################
    # GET SCAN TR_ID ITERATOR
    scan_infosource = Node(util.IdentityInterface(fields=['TR_id']), name='scan_infosource')
    scan_infosource.iterables = ('TR_id', TR_list)

    subjects_infosource = Node(util.IdentityInterface(fields=['subject_id']), name='subjects_infosource')
    subjects_infosource.iterables = ('subject_id', subjects_list)

    def add_subject_id_to_ds_dir_fct(subject_id, ds_path):
        import os
        out_path = os.path.join(ds_path, subject_id)
        return out_path

    add_subject_id_to_ds_dir = Node(util.Function(input_names=['subject_id', 'ds_path'],
                                                  output_names=['out_path'],
                                                  function=add_subject_id_to_ds_dir_fct),
                                    name='add_subject_id_to_ds_dir')
    wf.connect(subjects_infosource, 'subject_id', add_subject_id_to_ds_dir, 'subject_id')
    add_subject_id_to_ds_dir.inputs.ds_path = ds_dir

    wf.connect(add_subject_id_to_ds_dir, 'out_path', ds, 'base_directory')



   # get atlas data
    templates_atlases = {'FSL_MNI_3mm_template': 'MNI152_T1_3mm_brain.nii.gz',
                         }

    selectfiles_anat_templates = Node(nio.SelectFiles(templates_atlases,
                                                      base_directory=template_dir),
                                      name="selectfiles_anat_templates")

    # GET SUBJECT SPECIFIC FUNCTIONAL AND STRUCTURAL DATA
    selectfiles_templates = {
        'epi_2_MNI_warp': '{subject_id}/rsfMRI_preprocessing/registration/epi_2_MNI_warp/TR_{TR_id}/*.nii.gz',
        'preproc_epi_full_spectrum': '{subject_id}/rsfMRI_preprocessing/epis/01_denoised/TR_{TR_id}/*.nii.gz',
        'preproc_epi_bp': '{subject_id}/rsfMRI_preprocessing/epis/02_denoised_BP/TR_{TR_id}/*.nii.gz',
        'preproc_epi_bp_tNorm': '{subject_id}/rsfMRI_preprocessing/epis/03_denoised_BP_tNorm/TR_{TR_id}/*.nii.gz',
    }

    selectfiles = Node(nio.SelectFiles(selectfiles_templates,
                                       base_directory=preprocessed_data_dir),
                       name="selectfiles")
    wf.connect(scan_infosource, 'TR_id', selectfiles, 'TR_id')
    wf.connect(subjects_infosource, 'subject_id', selectfiles, 'subject_id')



    # CREATE TS IN MNI SPACE
    epi_MNI_01_denoised = Node(fsl.ApplyWarp(), name='epi_MNI_01_denoised')
    epi_MNI_01_denoised.inputs.interp = 'spline'
    epi_MNI_01_denoised.plugin_args = {'submit_specs': 'request_memory = 4000'}
    wf.connect(selectfiles, 'preproc_epi_full_spectrum', epi_MNI_01_denoised, 'in_file')
    wf.connect(selectfiles, 'epi_2_MNI_warp', epi_MNI_01_denoised, 'field_file')
    wf.connect(selectfiles_anat_templates, 'FSL_MNI_3mm_template', epi_MNI_01_denoised, 'ref_file')
    epi_MNI_01_denoised.inputs.out_file = 'preprocessed_fullspectrum_MNI_3mm.nii.gz'

    wf.connect(epi_MNI_01_denoised, 'out_file', ds, 'rsfMRI_preprocessing.epis_MNI_3mm.01_denoised')



    epi_MNI_03_bp_tNorm = Node(fsl.ApplyWarp(), name='epi_MNI_03_bp_tNorm')
    epi_MNI_03_bp_tNorm.inputs.interp = 'spline'
    epi_MNI_03_bp_tNorm.plugin_args = {'submit_specs': 'request_memory = 4000'}
    wf.connect(selectfiles, 'preproc_epi_bp_tNorm', epi_MNI_03_bp_tNorm, 'in_file')
    wf.connect(selectfiles, 'epi_2_MNI_warp', epi_MNI_03_bp_tNorm, 'field_file')
    wf.connect(selectfiles_anat_templates, 'FSL_MNI_3mm_template', epi_MNI_03_bp_tNorm, 'ref_file')
    epi_MNI_03_bp_tNorm.inputs.out_file = 'residual_filt_norm_warp.nii.gz'

    wf.connect(epi_MNI_03_bp_tNorm, 'out_file', ds, 'rsfMRI_preprocessing.epis_MNI_3mm.03_denoised_BP_tNorm')


    #####################################
    # RUN WF
    #####################################
    wf.write_graph(dotfilename=wf.name, graph2use='colored', format='pdf')  # 'hierarchical')
    wf.write_graph(dotfilename=wf.name, graph2use='orig', format='pdf')
    wf.write_graph(dotfilename=wf.name, graph2use='flat', format='pdf')

    if plugin_name == 'CondorDAGMan':
        wf.run(plugin=plugin_name)
    if plugin_name == 'MultiProc':
        wf.run(plugin=plugin_name, plugin_args={'n_procs': use_n_procs})
