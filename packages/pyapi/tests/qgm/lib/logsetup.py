#!/usr/bin/env python
# -*- mode: Python; coding: utf-8 -*-
"""
Created on Wed Apr 19 11:25:45 2017

@author: Konrad

This module handles the logging setup.

Adapted from https://docs.python.org/2/howto/logging.html

Adding dedicated logging handler for main gui window (only called if using
    gui).

TODO: add feature to have different logger for each gui module, indicating
current hdf5 file

"""

import logging
import logging.config
import os.path as osp

class QTextEditLoggingHandler(logging.Handler):
    '''
    Dedicated logging handler to make output in a QTextEdit widget
    '''
    def __init__(self, parentwidget):
        super(QTextEditLoggingHandler, self).__init__()
        self.widget = parentwidget
        self.widget.setReadOnly(True)
        #self.setFormatter(logging.Formatter(LOGGING['formatters']['detailed']))
    def emit(self, record):
        msg = self.format(record)
#        self.widget.appendPlainText(msg)
        self.widget.append(msg)

##Delete ipython notebook root logger handler
#log = logging.getLogger()
#log.handlers = []

# create logger
log = logging.getLogger('analyserlogger')
log.setLevel(logging.DEBUG)

#add handlers if none exist (may exist in iPython console)
if not log.handlers:
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    
    # create formatter
    formatter = logging.Formatter('%(asctime)s || %(levelname)s || %(message)s')
    
    # add formatter to ch
    ch.setFormatter(formatter)
    
    # add ch to logger
    log.addHandler(ch)

## 'application' code
#log.debug('debug message')
#log.info('info message')
#log.warn('warn message')
#log.error('error message')
#log.critical('critical message')