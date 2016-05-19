import nipype.pipeline.engine as pe
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio
from nipype.interfaces.freesurfer import SampleToSurface

'''directories'''
preprocDir = "/scr/adenauer1/Franz/nki_nilearn"
freesurferDir = "/scr/ilz2/nilearn_vol2surf_wd/freesurfer"
workingDir = "/scr/ilz2/nilearn_vol2surf_wd/"
sinkDir = "/scr/ilz1/nilearn_vol2surf_sink/"

'''subjects'''
subjects = []
with open('/scr/ilz1/nilearn_vol2surf_sink/subjects.txt') as f:
    subjects = f.read().splitlines()

'''workflow'''
if __name__ == '__main__':
    wf = pe.Workflow(name="map_to_surface")
    wf.base_dir = workingDir
    wf.config['execution']['crashdump_dir'] = wf.base_dir + "/crash_files"

    subjects_infosource = pe.Node(util.IdentityInterface(fields=['subject_id']), name="subjects_infosource")
    subjects_infosource.iterables = ('subject_id', subjects)

    hemi_infosource = pe.Node(util.IdentityInterface(fields=['hemi']), name="hemi_infosource")
    hemi_infosource.iterables = ('hemi', ['lh', 'rh'])

    datagrabber = pe.Node(nio.DataGrabber(infields=['subject_id'],
                                          outfields=['resting']),
                          name="datagrabber")
    datagrabber.inputs.base_directory = preprocDir
    datagrabber.inputs.template = '%s/residual_filt_norm_warp.nii.gz'
    datagrabber.inputs.template_args['resting'] = [['subject_id']]
    datagrabber.inputs.sort_filelist = True
    datagrabber.inputs.raise_on_empty = False

    vol2surf = pe.Node(SampleToSurface(mni152reg=True, 
				       target_subject='fsaverage5',
				       subjects_dir=freesurferDir,
                                       cortex_mask=True,
                                       sampling_method="average",
                                       sampling_range=(0.2, 0.8, 0.1),
                                       sampling_units="frac",
                                       smooth_surf=0.0,
				       args="--out_type GIFTI"),
                       name='vol2surf_lsd')


    def gen_out_file(subject_id, hemi):
        return "%s_%s_preprocessed_fsaverage5_fwhm0.gii" % (subject_id, hemi)
    output_name = pe.Node(util.Function(input_names=['subject_id', 'hemi'],
                                        output_names=['name'],
                                        function=gen_out_file),
                          name="output_name")

    datasink = pe.Node(nio.DataSink(parameterization=False, base_directory=sinkDir), name='sinker')

    wf.connect([(subjects_infosource, datagrabber, [('subject_id', 'subject_id')]),
                (hemi_infosource, vol2surf, [('hemi', 'hemi')]),


                (subjects_infosource, output_name, [('subject_id', 'subject_id')]),
                (hemi_infosource, output_name, [('hemi', 'hemi')]),
                (datagrabber, vol2surf, [('resting', 'source_file')]),
                (output_name, vol2surf, [('name', 'out_file')]),
                (vol2surf, datasink, [('out_file', '@rest_surf')])
                ])

    wf.run()


