"""
`dacman.core.diff`
====================================

.. currentmodule:: dacman.core.diff

:platform: Unix, Mac
:synopsis: Module finding `diff` between two datasets

.. moduleauthor:: Devarshi Ghoshal <dghoshal@lbl.gov>

"""

try:
   from os import scandir, walk
except ImportError:
   from scandir import scandir, walk

import yaml
import sys
import os
import uuid
import difflib
import time

import dacman.core.change as change
import dacman.core.analyzer as analyzer
import dacman.core.utils as utils
from dacman.core.utils import cprint, get_hash_id
import dacman.core.utils as dacman_utils

import subprocess
import multiprocessing

import logging

try:
   from mpi4py import MPI
   MPI4PY_IMPORT = True
except ImportError:
   MPI4PY_IMPORT = False

try:
   import tigres
   TIGRES_IMPORT = True
except ImportError:
   TIGRES_IMPORT = False

__modulename__ = 'diff'

class Differ(object):
    DEFAULT_EXECUTOR = 0
    MPI_EXECUTOR = 1
    TIGRES_EXECUTOR = 2

    def __init__(self, diff_all=False, custom_analyzer=None, executor=DEFAULT_EXECUTOR, outdir=None):
        self.old_path = None
        self.new_path = None
        self.deducedir = dacman_utils.DACMAN_STAGING_LOC
        self.old_deducedir = None
        self.new_deducedir = None
        self._diff_all = diff_all
        self.custom_analyzer = custom_analyzer
        self.diff_analyzer = analyzer.Analyzer()
        self.diffdir = None
        self.diff_pairs = []
        self.executor = executor
        self.outdir = outdir
        self.save_changes = False
        if outdir is not None:
           self.save_changes = True
        self.logger = logging.getLogger(__name__)

    def set_paths(self, old_path, new_path, custom_deducedir=None):
        self.old_path = os.path.abspath(old_path)
        self.new_path = os.path.abspath(new_path)
        if custom_deducedir:
           self.deducedir = custom_deducedir
        self.old_deducedir = os.path.join(self.deducedir, get_hash_id(self.old_path))
        self.new_deducedir = os.path.join(self.deducedir, get_hash_id(self.new_path))


    '''
    calculating longest common substring between two paths to avoid relative path queries
    '''
    def common_path(self, total_path, actual_path):
        match = difflib.SequenceMatcher(None, actual_path, total_path).find_longest_match(0, len(actual_path), 0, len(total_path))
        matched_path = actual_path[match.a: match.a+match.size]
        return matched_path


    '''
    find the old and new base directories which are indexed through deduce
    '''
    def get_path_prefixes(self):
       deduce_change = os.path.join(self.new_deducedir, 'CHANGE')
       with open(deduce_change, 'r') as f:
          change_info = yaml.load(f)
          for new_basepath in change_info:
             if self.new_path.startswith(new_basepath):
                for old_basepath in change_info[new_basepath]:
                   if self.old_path.startswith(old_basepath):
                      return (new_basepath, old_basepath)
                    


       '''
       #TODO: this needs to be changed as it won't work for custom deduce dirs 
       deducepath = change.find_deduce(os.path.abspath(path))
       path_prefix = os.path.dirname(deducepath)
       return path_prefix
       '''

    '''
    get the file pairs that have changed
    '''
    def get_change_pairs(self):
        if not (self.old_path and self.new_path):
            #cprint(__modulename__, 'Old and new datapaths are not specified!')
            self.logger.error('Old and new datapaths are not specified!')
            sys.exit()

        if not os.path.exists(self.old_path):
           #cprint(__modulename__, 'Path `{}` does not exist'.format(self.old_path))
           self.logger.error('Path %s does not exist', self.old_path)           
           sys.exit()

        if not os.path.exists(self.new_path):
           #cprint(__modulename__, 'Path `{}` does not exist'.format(self.new_path))
           self.logger.error('Path %s does not exist', self.new_path)           
           sys.exit()

        old_path_is_file = os.path.isfile(self.old_path)
        new_path_is_file = os.path.isfile(self.new_path)
        old_base = self.old_path
        new_base = self.new_path
        change_pairs = []
        self.logger.info('Starting diff calculation')
        if old_path_is_file and new_path_is_file:
            old_base = os.path.dirname(self.old_path)
            new_base = os.path.dirname(self.new_path)
            if old_base == new_base:
               change_pairs.append((self.old_path, self.new_path))
               return change_pairs
        elif old_path_is_file != new_path_is_file:
            #cprint(__modulename__, 'Datapaths are of different types')
            self.logger.error('Datapaths are of different types')
            sys.exit()
                    

        '''
        The code below allows to check for a diff between any two random files
        '''
        #cprint(__modulename__, 'Starting diff calculation')
        
        change_data = change.changes(old_base, new_base, self.deducedir)
                                     #self.old_deducedir,
                                     #self.new_deducedir)
        changes = change_data.modified

        self.logger.info('Searching for path indexes')

        if not self.old_deducedir:
           #self.old_deducedir = change.find_deduce(old_base)
           self.old_deducedir = os.path.join(self.deducedir, get_hash_id(old_base))
        if not self.new_deducedir:
           #self.new_deducedir = change.find_deduce(new_base)
           self.new_deducedir = os.path.join(self.deducedir, get_hash_id(new_base))

        '''
        find the old and new base directories which are indexed through deduce
        '''
        path_prefixes = self.get_path_prefixes()
        path_prefix_new = path_prefixes[0]
        path_prefix_old = path_prefixes[1]
        '''
        save the metadata about the high-level diff between the directories
        '''
        if not old_path_is_file:
           if self.save_changes:
              self.__save_dir_diff__(change_data)
              self.logger.info('Change summary saved in: %s', self.outdir)
           change.display(change_data)           
           '''
           for each file level change, a detailed change analysis is reqd
           '''
           for change_key in changes:
              new_path = os.path.join(path_prefix_new, change_key)
              old_path = os.path.join(path_prefix_old, changes[change_key])
              change_pairs.append((new_path, old_path))
        else:
           rel_new_path = os.path.relpath(self.new_path, path_prefix_new)
           rel_old_path = os.path.relpath(self.old_path, path_prefix_old)
           if rel_new_path in changes and changes[rel_new_path] == rel_old_path:
              change_pairs.append((self.new_path, self.old_path))

        return change_pairs


    '''
    summary of changes (at a high-level, no data-level)
    '''
    def diff_summary(self, change_pairs):
        if len(change_pairs) == 0:
           #cprint(__modulename__, 'There is no data change between files in datasets: {} -> {}'.format(self.old_path, self.new_path))
           print('There is no change in the datasets')
        elif len(change_pairs) == 1:
           if os.path.isfile(self.old_path):
              #cprint(__modulename__, 'Files {} and {} differ'.format(self.new_path, self.old_path))
              print('Files {} and {} changed'.format(self.new_path, self.old_path))
           else:
              #cprint(__modulename__, '1 file differs in {} and {}'.format(self.new_path, self.old_path))
              #print('Total modified: 1')
              pass
        else:
           #cprint(__modulename__, '{} files differ in {} and {}'.format(len(change_pairs),
           #                                                             self.new_path,
           #                                                             self.old_path))
           #print('Total modified: {}'.format(len(change_pairs)))
           pass


    '''
    saves directory changes
    '''
    def __save_dir_diff__(self, change_data):
       SUMMARY_METAFILE = 'summary'
       ADDED_METAFILE = 'added'
       DELETED_METAFILE = 'deleted'
       MODIFIED_METAFILE = 'modified'
       METADATA_ONLY_METAFILE = 'metaonly'
       UNCHANGED_METAFILE = 'unchanged'

       #cprint(__modulename__, 'Saving directory-level changes')
       #cprint(__modulename__, 'Saving file changes')
       self.logger.info('Saving summary of changes')
       curdir = os.getcwd()
       #outdir = hashlib.md5('{}{}'.format(self.old_path, self.new_path).encode('utf-8')).hexdigest()
       #outdir = utils.hash_comparison_id(self.old_path, self.new_path)
       #outdir = os.path.join(curdir, outdir)
       outdir = self.outdir

       if not os.path.exists(outdir):
          os.makedirs(outdir)
       summary_file = os.path.join(outdir, SUMMARY_METAFILE)

       change_summary = {}
       #change_summary['versions'] = {self.new_path: self.old_path}
       change_summary['versions'] = {'base': {'dataset_id': change_data.old_path, 
                                              'nfiles': change_data.old_nfiles},
                                     'revision': {'dataset_id': change_data.new_path,
                                                  'nfiles': change_data.new_nfiles}}
       change_summary['counts'] = change_data.get_change_map()
       #change_summary['degree'] = change_data.degree
       # REMOVED: change_factor, as it is not a useful change metric 
       #change_summary['change_factor'] = change_data.degree # * 100
       utils.dump_yaml(change_summary, summary_file)

       '''
       info_file = os.path.join(outdir, 'change.info')
       change_info = {'modified': change_data.modified,
                      'deleted': change_data.deleted,
                      'added': change_data.added,
                      'metaonly': change_data.metachange}
       utils.dump_yaml(change_info, info_file)
       '''
       add_change_file = os.path.join(outdir, ADDED_METAFILE)
       del_change_file = os.path.join(outdir, DELETED_METAFILE)
       mod_change_file = os.path.join(outdir, MODIFIED_METAFILE)
       meta_change_file = os.path.join(outdir, METADATA_ONLY_METAFILE)
       unchanged_meta_file = os.path.join(outdir, UNCHANGED_METAFILE)
       
       if len(change_data.added) > 0:
          utils.list_to_file(change_data.added, add_change_file)
       if len(change_data.deleted) > 0:
          utils.list_to_file(change_data.deleted, del_change_file)
       if len(change_data.modified) > 0:
          utils.dict_to_file(change_data.modified, mod_change_file)
       if len(change_data.metachange) > 0:
          utils.dict_to_file(change_data.metachange, meta_change_file)
       if len(change_data.unchanged) > 0:
          utils.list_to_file(change_data.unchanged, unchanged_meta_file)

       #change.display(change_data)
       #cprint(__modulename__, 'Change information saved in: {}'.format(outdir))
       #cprint(__modulename__, 'Change information saved in: {}'.format(outdir))

#########################################################################################################

    '''
    main diff function that calculates differences between files or directories
    '''    
    def diff(self):
       if self.old_path == self.new_path:
          self.logger.error('Diff paths are the same')
          sys.exit()

       if self.executor == Differ.DEFAULT_EXECUTOR:
          #self.logger.info('Calculating summary of changes')
          change_pairs = self.get_change_pairs()
          self.diff_summary(change_pairs)
          if self._diff_all and len(change_pairs) > 0:
              #cprint(__modulename__, 'Comparing diffs between all files in the directory using Python multiprocessing')
              self.logger.info('Using Python multiprocessing for calculating data changes in modified files')
              self.collection_diff_default(change_pairs)
       elif self.executor == Differ.MPI_EXECUTOR:
          if not MPI4PY_IMPORT:
             #cprint(__modulename__, 'mpi4py not installed (required for the mpi executor). Exiting...')
             self.logger.error('mpi4py is not installed or possibly not in the path')
             sys.exit()
          self.logger.info('Using MPI for calculating data changes in modified files')
          self.collection_diff_mpi()
       elif self.executor == Differ.TIGRES_EXECUTOR:
          if not TIGRES_IMPORT:
             #cprint(__modulename__, 'Tigres not installed (required for the tigres executor). Exiting...')
             self.logger.error('Tigres is not installed or possibly not in the path')
             sys.exit()
          #self.logger.info('Calculating summary of changes')
          change_pairs = self.get_change_pairs()
          self.diff_summary(change_pairs)
          if self._diff_all and len(change_pairs) > 0:
              #cprint(__modulename__, 'Comparing diffs between all files in the directory using Tigres')
              self.logger.info('Using Tigres for calculating data changes in modified files')
              self.collection_diff_tigres(change_pairs)
       
       self.logger.info('Diff completed')


#########################################################################################################

    '''
    function to calculate diffs between two files using the specified analyzer
    '''
    def file_diff(self, new_file, old_file):
       #cprint(__modulename__, 'Calculating diffs between {} and {}'.format(new_file, old_file))
       self.logger.info('Calculating changes in %s and %s', new_file, old_file)
       self.diff_pairs.append((new_file, old_file))
       if not self.custom_analyzer:
          #cprint(__modulename__, 'Using default deduce analyzer')
          logger.info("Using default analyzer")
          output = self.diff_analyzer.analyze(new_file, old_file)
          if output != None and output.strip() != '':
             print(output)
       elif callable(self.custom_analyzer):
          #cprint(__modulename__, 'Using custom function analyzer: {}'.format(self.custom_analyzer.__name__))
          logger.info("Using custom function analyzer %s", self.custom_analyzer.__name__)
          output = self.custom_analyzer(new_file, old_file)
          if output != None and output.strip() != '':
             print(output)
       elif isinstance(self.custom_analyzer, str):
          self.logger.info('Using custom executable analyzer %s', custom_analyzer)
          #cprint(__modulename__, 'Using custom executable analyzer: {}'.format(self.custom_analyzer))
          logger.info("Using custom executable analyzer %s", self.custom_analyzer)
          output = self.executable_diff(new_file, old_file)
          if output != None and output.strip() != '':
             #print(output)
             print(output.decode(sys.stdout.encoding).strip())
       else:
          self.logger.error('Analyzer type %s is not supported', type(custom_analyzer))
          raise TypeError('Analyzer type {} not supported'.format(type(custom_analyzer)))
                
#########################################################################################################

    '''
    function to calculate diffs between two files using an external script or app
    '''
    def executable_diff(self, new_file, old_file):
        proc = subprocess.Popen([self.custom_analyzer, new_file, old_file],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if err:
            #cprint(__modulename__, 'Error: {}'.format(err))
            self.logger.error('Error analyzing changes: %s', err)
            return None
        else:
            #cprint(__modulename__, 'Output: {}'.format(out))
            self.logger.info('Change calculation completed with output: %s', out)
            return out

#########################################################################################################
        
    '''
    function to calculate diffs in a collection of file-pairs using
    the default executor (Python multiprocessing)
    '''
    def collection_diff_default(self, change_pairs):
       #cprint(__modulename__, 'Using Python multiprocessing for parallel change calculation')
       num_procs = multiprocessing.cpu_count()
       results = []
       pool = multiprocessing.Pool(processes=num_procs)
       for change_pair in change_pairs:
          #result = pool.apply_async(file_diff, args=(change_pair[0], change_pair[1]))
          result = pool.apply_async(file_diff_mp, args=(change_pair[0], change_pair[1], 
                                                        self.custom_analyzer, self.diff_analyzer))
          results.append(result)

       pool.close()
       pool.join()

#########################################################################################################

    def collection_diff_mpi(self):
       comm = MPI.COMM_WORLD
       size = comm.Get_size()
       rank = comm.Get_rank()
       status = MPI.Status()
    
       class States():
          READY = 0
          START = 1
          DONE = 2
          EXIT = 3

       if rank == 0:        
          change_pair_num = 0
          closed_workers = 0
          num_workers = size - 1
          
          #self.logger.info('Calculating summary of changes')
          change_pairs = self.get_change_pairs()
          self.diff_summary(change_pairs)
          if self._diff_all:
              #cprint(__modulename__, 'Comparing diffs between all files in the directory using MPI')
              change_pairs = self.get_change_pairs()

              while closed_workers < num_workers:
                 result = comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
                 source = status.Get_source()
                 tag = status.Get_tag()
            
                 if tag == States.READY:
                    if change_pair_num < len(change_pairs):
                       comm.send(change_pairs[change_pair_num], dest=source, tag=States.START)
                       change_pair_num += 1
                    else:
                       comm.send(None, dest=source, tag=States.EXIT)
                 elif tag == States.DONE:
                    pass
                 elif tag == States.EXIT:
                    closed_workers += 1
       else:
          # only start parallel processing if data change is required
          if self._diff_all:
             while True:
                comm.send(None, dest=0, tag=States.READY)
                change_pair = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
                tag = status.Get_tag()

                if tag == States.START:
                   new_file = change_pair[0]
                   old_file = change_pair[1]
                   self.file_diff(new_file, old_file)
                   comm.send(None, dest=0, tag=States.DONE)
                elif tag == States.EXIT:
                   comm.send(None, dest=0, tag=States.EXIT)
                   break

#########################################################################################################

    '''
    function to calculate diffs in a collection of file-pairs using
    the Tigres executor
    '''
    def collection_diff_tigres(self, change_pairs):
        exec_name = 'EXECUTION_DISTRIBUTE_PROCESS'
        exec_plugin = tigres.utils.Execution.get(exec_name)

        try:
            logfile = 'deduce_diff_{}.log'.format(str(round(time.time())))
            tigres.start(name='deduce_diff', log_dest=logfile, execution=exec_plugin)
            tigres.set_log_level(tigres.Level.ERROR)

            task_array = tigres.TaskArray(tasks=[])
            input_array = tigres.InputArray(values=[])
        
            if not self.custom_analyzer:
                task_diff = tigres.Task("diff_file", task_type=tigres.FUNCTION,
                                        impl_name=self.file_diff)
                task_array.append(task_diff)
            elif isinstance(self.custom_analyzer, str):
                task_diff = tigres.Task("diff_file", task_type=tigres.EXECUTABLE,
                                        impl_name=self.custom_analyzer)
                task_array.append(task_diff)
            elif callable(self.custom_analyzer):
                task_diff = tigres.Task("diff_file", task_type=tigres.FUNCTION,
                                        impl_name=self.custom_analyzer)
                task_array.append(task_diff)
            elif isinstance(self.custom_analyzer, list):
                if len(self.custom_analyzer) != len(change_pairs):
                    #cprint(__modulename__, 'Number of analyzers do not match the number of comparisons')
                    self.logger.error('Number of Tigres analyzers do not match the number of comparisons')
                    sys.exit()
                for a in self.custom_analyzer:
                    task_name = 'task_diff'
                    if callable(a):
                        task_type = tigres.FUNCTION
                    else:
                        task_type = tigres.EXECUTABLE
                    task_array.append(tigres.Task(task_name, task_type=task_type, impl_name=a))
        
            for change_pair in change_pairs:
                self.diff_pairs.append((change_pair[0], change_pair[1]))
                input_array.append(tigres.InputValues(list_=[change_pair[0], change_pair[1]]))

            diff_paths = tigres.parallel('diff_files', input_array=input_array,
                                         task_array=task_array)

        except tigres.utils.TigresException as e:
            print(str(e))
            return_code = 1    
        finally:
            tigres.end()

#########################################################################################################

'''
TODO: duplicate code that needs to be fixed -- used by python multiprocessing to launch executables.
'''
def file_diff_mp(new_file, old_file, custom_analyzer, diff_analyzer):
   logger = logging.getLogger(__name__)
   logger.info('Calculating changes in %s and %s', new_file, old_file)
   if not custom_analyzer:
      logger.info("Using default analyzer")
      output = diff_analyzer.analyze(new_file, old_file)
      if output != None and output.strip() != '':
         print(output)
   elif callable(custom_analyzer):
      logger.info("Using custom function analyzer %s", custom_analyzer.__name__)
      output = custom_analyzer(new_file, old_file)
      if output != None and output.strip() != '':
         print(output)
   elif isinstance(custom_analyzer, str):
      logger.info("Using custom executable analyzer %s", custom_analyzer)
      output = executable_diff_mp(new_file, old_file, custom_analyzer)
      if output != None and output.strip() != '':
         print(output.decode(sys.stdout.encoding).strip())
         #sys.stdout.write(output)
         #sys.stdout.flush()
      #logger.info("Output: %s", output)
   else:
      logger.error('Analyzer type %s is not supported', type(custom_analyzer))
      raise TypeError('Analyzer type {} not supported'.format(type(custom_analyzer)))


def executable_diff_mp(new_file, old_file, custom_analyzer):
   logger = logging.getLogger(__name__)
   proc = subprocess.Popen([custom_analyzer, new_file, old_file],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   out, err = proc.communicate()
   if err:
      logger.error('Error analyzing changes: %s', err)
      return None
   else:
      logger.info('Change calculation completed with output: %s', out)
      return out
                
#########################################################################################################

'''
test custom analyzer
'''
def myanalyzer(file1, file2):
    print('My custom analyzer for calculating changes between {} and {}'.format(file1, file2))

def main(args):
    oldpath = args.oldpath
    newpath = args.newpath
    deducedir = args.stagingdir
    analyzer = args.analyzer
    recursive = args.datachange
    outdir = args.outdir

    executor_map = {'default': Differ.DEFAULT_EXECUTOR,
                    'mpi': Differ.MPI_EXECUTOR,
                    'tigres': Differ.TIGRES_EXECUTOR}
    executor = executor_map[args.executor]

    differ = Differ(recursive, analyzer, executor, outdir)
    differ.set_paths(oldpath, newpath, deducedir)
    differ.diff()

def s_main(args):
    oldpath = args['oldpath']
    newpath = args['newpath']
    olddeducedir = None
    newdeducedir = None
    #analyzer = myanalyzer
    analyzer = None
    recursive = False
    if 'olddeducedir' in args:
       olddeducedir = args['olddeducedir']
    if 'newdeducedir' in args:
       newdeducedir = args['newdeducedir']
    if 'analyzer' in args:
       analyzer = args['analyzer']
    if 'datachange' in args:
       datachange = args['datachange']

    #differ = Differ(oldpath, newpath, olddeducedir, newdeducedir, recursive, analyzer)
    differ = Differ(recursive, analyzer)
    differ.set_paths(oldpath, newpath, olddeducedir, newdeducedir)
    differ.diff()

if __name__ == '__main__':
   args = {'oldpath': sys.argv[1], 'newpath': sys.argv[2]}

   s_main(args)