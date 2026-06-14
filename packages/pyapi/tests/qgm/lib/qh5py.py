# -*- coding: utf-8 -*-
"""
Created on Mon Dec 17 10:05:11 2012

@author: Christoph Gohle

A wrapper around h5py that supports some special data types that are not natively
supported. Specifically, numbers with units get native support here.
It also supports assigning dictionaries to groups. Then each k,v pair will be added
to the data as a named dataset to the group that was assigned. Obviously, only 
string type keys are supported.
"""

import h5py as h
UNITATTR = 'unit'
import os.path as osp

#place all names from h5py here as well except for those that we extend

selfdefnames = ('Group', 'Dataset', 'AttributeManager', 'File', '__file__', 
                '__name__', '__package__', '__path__', '__doc__')
                
for n in dir(h):
    if n not in selfdefnames:
        globals()[n] = getattr(h,n)

class Group(h.Group):
    def __init__(self, *args, **kwargs):
        self._sm = kwargs.pop('sm', None)
        super(Group, self).__init__(*args, **kwargs)
        
    def create_group(self, name):
        s = super(Group, self).create_group(name)
        return Group(s._id, sm = self)
        
    def create_dataset(self, name, shape = None, dtype = None, data=None, **kwds):
        s = super(Group, self).create_dataset(name, shape, dtype, data, **kwds)
        if hasattr(data, UNITATTR):
            #assume this is something that has a unit (and a 'symbol' property)
            s.attrs[UNITATTR]=data.symbol
        else:
            pass
        return Dataset(s._id, sm = self)
        
    def __getitem__(self, name):
        res = super(Group, self).__getitem__(name)
        if isinstance(res, h.Dataset):
            res = Dataset(res._id, sm = self)
        elif isinstance(res, h.Group):
            res = Group(res._id, sm = self)
        return res
        
    def __setitem__(self, name, value):
        if hasattr(value, 'unit'):
            super(Group, self).__setitem__(name, value.value)
            self[name].attrs[UNITATTR] = value.symbol
        elif isinstance(value, dict):
            if name in self.keys():
                g = self[name]
            else:
                g = self.create_group(name)
                
            for k,v in value.iteritems():
                g[k]=v
        else:
            super(Group, self).__setitem__(name, value)

    @property
    def base(self):
        if self._sm is not None:
            return self._sm.base
        else:
            return self
    
    @property
    def attrs(self):
        return AttributeManager(self, sm = self)
        
    @attrs.setter
    def attrs(self, value):
        if not isinstance(value, dict):
            raise ValueError('only string valued dictionaries can be assigned to the attribute list')
        else:
            self.attrs.update(value)

class File(Group, h.File):
    def __init__(self, *args, **kwargs):
        self.close_callback = kwargs.pop('close_callback', None)
        self.cb_args = kwargs.pop('cb_args',())
        self._sm = None
        h.File.__init__(self, *args, **kwargs)
                        
    def __del__(self):
        if self.id.id is not 0:        
            self.close()
            
    def close(self):
        super(File, self).close()
        if self.close_callback is not None:
            self.close_callback(*self.cb_args)

    def __getstate__(self):
        return osp.abspath(self.filename)

    def __setstate__(self, state):
        h.File.__init__(self,state, 'r')
        
class Dataset(h.Dataset):
    def __init__(self, *args, **kwargs):
        self._sm = kwargs.pop('sm', False)
        super(Dataset, self).__init__(*args, **kwargs)

    @property
    def value(self):
        return self[()]
    
    def __getitem__(self, args):
        res = super(Dataset, self).__getitem__(args)
        return res
        
    def __setitem__(self, args, val):
        super(Dataset, self).__setitem__(args, val)

    @property
    def base(self):
        if self._sm is not None:
            return self._sm.base
        else:
            return self
            
    @property
    def attrs(self):
        return AttributeManager(self, sm = self)
    
    @attrs.setter
    def attrs(self, value):
        if not isinstance(value, dict):
            raise ValueError('only string valued dictionaries can be assigned to the attribute list')
        else:
            self.attrs.update(value)

class AttributeManager(h.AttributeManager):
    def __init__(self, *args, **kwargs):
        self._sm = kwargs.pop('sm', None)
        super(AttributeManager, self).__init__(*args,**kwargs)
        
    @staticmethod    
    def uattr(name):
        return '.%s.unit'%name
        
    def __getitem__(self, name):
        res = super(AttributeManager, self).__getitem__(name)
        return res
    
    def __setitem__(self, name, value):
        if hasattr(value, 'unit'):
            super(AttributeManager, self).__setitem__(name, value.value)
            super(AttributeManager, self).__setitem__(self.uattr(name), value.symbol)
        else:
            super(AttributeManager, self).__setitem__(name, value)

        base = self._sm.base            
        if hasattr(base,'readme'):
            fn = self._sm.name#.replace('/','_')
            if base.level is not None and fn.count('/')-1>base.level:
                #subgroup level exceeds given level -> don't store in readme
                return
            base.readme.set(name, value, fn, save=False)

    def update(self, dict):
        """update the attributes list with the contents of a dictionary.
        
        Obviously this only works for dictionaries with string type keys."""
        for k,v in dict.iteritems():
            self[k]=v
