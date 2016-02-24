__author__ = 'franzliem'


def zip_and_save_running_scripts(subject_id, script_dir):
    '''
    import subject to target into subject iterable folder structure
    '''
    import os, shutil

    target_dir = os.path.join(os.getcwd(), 'scripts_copy')
    zip_file = target_dir + '.zip'
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)
    if os.path.isfile(zip_file):
        os.remove(zip_file)

    shutil.copytree(script_dir, target_dir)
    shutil.make_archive(target_dir, format='zip', root_dir=target_dir)
    shutil.rmtree(target_dir)
    return zip_file


def get_condor_exit_status(batch_dir):
    import yaml
    import glob
    import os

    log_files = glob.glob(os.path.join(batch_dir, 'workflow*.dag.metrics'))
    log_files.sort(key=os.path.getmtime)
    # youngest file
    log_file = log_files[-1]
    f = open(log_file)
    d = yaml.load(f)
    f.close()

    return (d['exitcode'], d['jobs_failed'])  # int 0:ok; >0:not ok


def check_if_wf_crashed(crash_dir):
    import os
    wf_crashed = False
    if os.path.exists(crash_dir):
        if os.listdir(crash_dir):
            wf_crashed = True
    return wf_crashed


def load_subjects_list(subjects_dir, file):
    '''loads a text file with subject names into a list
    text file example:
    ...
    0152992
    0189478
    ...
    '''
    import os
    subjects_file = os.path.join(subjects_dir, file)
    with open(subjects_file, 'r') as f:
        subjects_list = [line.strip() for line in f]
    subjects_list = filter(None,subjects_list)
    return subjects_list


def get_subjects_list_fold(subjects_list,fold_n,fold_size):
    '''
    returns folds of subjects_list
    :param subjects_list:   full subjects_list
    :param fold_n:          starting with 0
    :param fold_size:       n subjects in fold
    :return:
    '''
    fold_start = fold_n * fold_size
    fold_end = fold_start + fold_size
    n_subjects = len(subjects_list)
    if fold_end > n_subjects:
        fold_end = n_subjects
    print('# # # # # # # # # # # # # # # # # # ')
    print( 'RUNNING FOLD no %s: subjects %s ... %s of %s subjects'%(fold_n, fold_start, fold_end-1, n_subjects) )
    print('# # # # # # # # # # # # # # # # # # ')
    return subjects_list[fold_start:fold_end]

