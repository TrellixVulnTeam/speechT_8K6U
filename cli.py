# Copyright 2017 Louis Kirsch. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import argparse
import os


from lazy import lazy

from evaluation import Evaluation
from parameter_search import LanguageModelParameterSearch
from recording import Recording
from training import Training


class CLI:

  def __init__(self):
    self.parser = argparse.ArgumentParser()
    self.subparsers = self.parser.add_subparsers(help='sub-command help', dest='command')
    self.base_parser = self._create_base_parser()
    self._add_training_parser()
    self._add_evaluation_parser()
    self._add_recording_parser()
    self._add_parameter_search_parser()

  def _create_base_parser(self):
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument('--mfcc', dest='feature_type', action='store_const', const='mfcc',
                             help='Use a mfccs as input.')
    base_parser.add_argument('--power', dest='feature_type', action='store_const', const='power',
                             help='Use a power spectrogram as input.')
    base_parser.add_argument('--batch-size', dest='batch_size', type=int, default=64,
                             help='Batch size to use.')
    base_parser.add_argument('--run-name', dest='run_name', type=str, default='noname',
                             help='Give this training a name to appear in tensorboard.')
    base_parser.add_argument('--data-dir', dest='data_dir', type=str, default='data',
                             help='Data directory.')
    base_parser.add_argument('--train-dir', dest='train_dir', type=str, default='train',
                             help='Training directory to store the runs in.')
    base_parser.add_argument('--log-dir', dest='log_dir', type=str, default='log',
                             help='Log directory to log the runs in.')
    base_parser.set_defaults(feature_type='power')
    return base_parser

  def _add_training_parser(self):
    training_parser = self.subparsers.add_parser('train', help='Train the wav2letter weights.',
                                                 parents=[self.base_parser])
    training_parser.add_argument('--learning-rate', dest='learning_rate', type=float, default=1e-3,
                                 help='The initial learning rate.')
    training_parser.add_argument('--reset-learning-rate', dest='reset_learning_rate', action='store_true',
                                 help='Reset the learning rate to the default or provided value.')
    training_parser.add_argument('--learning-rate-decay-factor', dest='learning_rate_decay_factor',
                                 type=float, default=0,
                                 help='Enable learning rate decay, decays by the given factor.')
    training_parser.add_argument('--momentum', dest='momentum', type=float, default=0.9,
                                 help='Optimizer momentum.')
    training_parser.add_argument('--max-gradient-norm', dest='max_gradient_norm', type=float, default=5.0,
                                 help='Clip gradients to this norm.')
    training_parser.add_argument('--limit-training-set', dest='limit_training_set', type=int, default=0,
                                 help='Train on a smaller training set, limited to the specified size')
    training_parser.add_argument('--steps-per-checkpoint', dest='steps_per_checkpoint', type=int, default=1000,
                                 help='How many training steps to do per checkpoint.')

  def _add_language_model_argument(self, parser: argparse.ArgumentParser):
    parser.add_argument('--language-model', dest='language_model', type=str,
                        help='Use beam search with given language model. '
                             'Specify a directory containing `kenlm-model.binary`, '
                             '`vocabulary` and `trie`. '
                             'Language model must be binary format with probing hash table.')

  def _add_evaluation_parser(self):
    evaluation_parser = self.subparsers.add_parser('evaluate', help='Evaluate the development or test set.',
                                                   parents=[self.base_parser])
    evaluation_parser.add_argument('--dev', dest='dataset', action='store_const', const='dev',
                                   help='Use the development dataset.')
    evaluation_parser.add_argument('--test', dest='dataset', action='store_const', const='test',
                                   help='Use the test dataset.')
    evaluation_parser.add_argument('--no-save', dest='should_save', action='store_false',
                                   help='Do not save evaluation')
    evaluation_parser.add_argument('--epoch-count', dest='epoch_count', type=int, default=1,
                                   help='Number of epochs to evaluate')
    self._add_language_model_argument(evaluation_parser)
    evaluation_parser.set_defaults(dataset='test')

  def _add_recording_parser(self):
    recording_parser = self.subparsers.add_parser('record', help='Record using your microphone and inspect'
                                                                 'the transcription.',
                                                  parents=[self.base_parser])
    recording_parser.add_argument('--input-size', dest='input_size', type=int, default=128,
                                  help='The input size of each sample, depending on what preprocessing was used')
    self._add_language_model_argument(recording_parser)

  def _add_parameter_search_parser(self):
    parameter_search_parser = self.subparsers.add_parser('search', help='Search for language model hyper parameters'
                                                                        'using local search.',
                                                         parents=[self.base_parser])
    parameter_search_parser.add_argument('--population-size', dest='population_size', type=int, default=10,
                                         help='The size of the population for the local search.')
    parameter_search_parser.add_argument('--noise-std', dest='noise_std', type=float, default=0.5,
                                         help='The standard deviation of the normal noise for mutation.')
    parameter_search_parser.add_argument('--ui', dest='use_ui', action='store_true',
                                         help='Whether to use an UI to print results.')
    self._add_language_model_argument(parameter_search_parser)

  @lazy
  def parsed(self):
    parsed = self.parser.parse_args()

    if parsed.command == 'train':
      parsed.run_type = 'train'
    elif parsed.command == 'evaluate':
      parsed.run_type = parsed.dataset
    elif parsed.command == 'record':
      parsed.run_type = 'record'
    else:
      parsed.run_type = 'other'

    parsed.run_train_dir = parsed.train_dir + '/' + parsed.run_name

    return parsed

  @lazy
  def command_executor(self):
    return {
      'train': Training,
      'evaluate': Evaluation,
      'record': Recording,
      'search': LanguageModelParameterSearch
    }[self.parsed.command](self.parsed)

  def run(self):
    self._ensure_directories()
    self.command_executor.run()

  def _ensure_directories(self):
    directories = [self.parsed.train_dir,
                   self.parsed.data_dir,
                   self.parsed.log_dir,
                   self.parsed.run_train_dir]
    for directory in directories:
      if not os.path.exists(directory):
        os.makedirs(directory)


if __name__ == "__main__":
  cli = CLI()
  cli.run()
