import _collections_abc
import sys as _sys
import types as _types

#####################################################
### Internal classes, constants, and variables. 
####################################################

# Minimum pydict size
_MIN_SIZE = 8

#Resize function
def _resize_pydict(pd, size):
    # Self is the pd
    self = pd
    # Get a copy of the items - now!
    items = tuple(self.items())
    # Double size
    self._size = size
    # Reset hash tables
    self._hash_table = [None] * self._size
    # Set all keys to their values
    for k, v in items:
        self[k] = v
    

#Ids of pydicts (or frozenpydicts) being repr'ed
_repr_pydicts = set()
        
        
class _Node(object):
    __slots__ = "hashcode", "key", "value", "overflow"
    def __init__(self, hashcode, key, value, overflow=None):
        self.hashcode = hashcode
        self.key = key
        self.value = value
        self.overflow = overflow
        
    def __eq__(self, other):
        if not isinstance(other, _Node):
            return NotImplemented
        return (self.hashcode, self.key, self.value, self.overflow) == \
               (other.hashcode, other.key, other.value, other.overflow)
        
    def __repr__(self):
        return "pydict._Node(hashcode={}, key={}, value={}, overflow={})".format(
            self.hashcode, repr(self.key), repr(self.value), self.overflow
        )
    
    def __sizeof__(self):
        # Note: Omit key and value because they aren't internal
        # Get size of self and size of self's hashcode
        size = object.__sizeof__(self) + int.__sizeof__(self.hashcode)
        # Get the size of all overflow nodes
        node = self
        while node.overflow != None:
            node = node.overflow
            size += object.__sizeof__(node) + int.__sizeof__(node.hashcode)
        # We are done! Return the total
        return size
    
    def copy(self):
        result = _Node(self.hashcode, self.key, self.value, self.overflow)
        n = result
        while isinstance(n.overflow, _Node):
            o = n.overflow
            n.overflow = _Node(o.hashcode, o.key, o.value, o.overflow)
            n = n.overflow
        return result
    
_marker = object()

####################################################
### pydict
####################################################     

class pydict(object):
    """Python implementation of builtins.dict
    
    pydict() -> new empty python dictionary
    pydict(mapping) -> new python dictionary initialized from the mapping's (key, value) pairs
    pydict(iterable) -> new python dictionary initialized via:
        p = pydict()
        for key, value in iterable:
            p[key] = value
    pydict(**kwds) -> new python dictionary initialized from the keyword arguments (name, value) pairs
    """
    
    __slots__ = (
        "_keys", "_hash_table", "_size"
    )
    
    def __new__(cls, mapping_or_iterable=(), /, **kwds):
        # Get a raw object from object.__new__
        self = object.__new__(cls)
        
        # Initiate private fields
        self._keys = []
        self._size = _MIN_SIZE
        self._hash_table = [None] * self._size
        
        # Update self using mapping_or_iterable and kwds
        self.update(mapping_or_iterable, **kwds)
        
        # Return the modified object
        return self
    
    __class_getitem__ = classmethod(_types.GenericAlias)
    
    def __contains__(self, key):
        "Return key in self."
        # Is this object in my keys?
        return key in self.keys()
    
    def __copy__(self):
        "Implement copy.copy(self)."
        return self.copy()
        
    def __delitem__(self, key):
        "Delete self[key]."
        # Ge the hash code of the key. Trim it to size.
        h = hash(key) % self._size
        # The previous node
        prev = None
        # The current node
        node = self._hash_table[h]
        # While the current node isn't None...
        while node is not None:
            # Is this the corresponding node?
            if node.hashcode == h and node.key == key:
                # If so, is there a previous node in the overflow chain?
                if prev is not None:
                    # If so, chain this node's overflow to the previous node's overflow
                    prev.overflow = node.overflow
                else:
                    # Otherwise, the node's overflow is the new reference in the hash slot
                    self._hash_table[h] = node.overflow
                # Remove the key from the pydict's keys
                self._keys.remove(key)
                # Avoid future iteration and the upcoming else statement
                break
            # Set the previous node to the current, the current to the current's overflow
            prev = node
            node = node.overflow
        else:
            # Raise KeyError
            raise KeyError(key)    
    
    def __eq__(self, other):
        "Return self==other"
        # Are self and other the same class? If not, return NotImplemented
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        # Check false with unequal length
        if len(self) != len(other):
            return False
        # Iterate over my keys
        for key in self:
            # If other[key] is absent or unequal to self[key]
            # Return False
            try:
                if self[key] != other[key]:
                    return False
            except KeyError:
                return False
        return True
    
    def __getitem__(self, key):
        "Return self[key]."
        # Get the hash value of the key. Trim it to be within
        # the size (# of buckets available)
        h = hash(key) % self._size
        # Get the result from the hash table.
        result = self._hash_table[h]
        # If there is no node, probe __missing__
        if result is None:
            return self.__missing__(key)
        # Set node to the first node
        node = result
        # Check for the correct node. If so return its value.
        if node.hashcode == h and node.key == key:
            return node.value
        # Search the overflow. Is the a correct node?
        while node.overflow is not None:
            node = node.overflow
            # If so, return its value.
            if node.hashcode == h and node.key == key:
                return node.value
        # There is no corresponding node. Probe missing.
        return self.__missing__(key)    
    
    # No hash code, as we are mutable.
    __hash__ = None
    
    def __ior__(self, value):
        "Return self|=value"
        self.update(value)
        return self
    
    def __iter__(self):
        "Return iter(self)"
        # Return the iterator of a copy of this object's keys
        return iter(self.keys())    
    
    def __len__(self):
        "Return len(self)."
        # Return the length of my keys.
        return len(self._keys)
    
    def __missing__(self, key):
        "Fallback method when self[key] fails. \nRaises KeyError(key) by default."
        raise KeyError(key)
    
    def __ne__(self, other):
        "Return self!=other"
        # Return the opposite of self==other
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        return not (self == other)
    
    def __or__(self, value):
        "Return self|value"
        pd = self.copy()
        return pd.__ior__(value)
    
    def __repr__(self):
        "Return repr(self)"
        # If within the midst of another repr call on the same object,
        # return a filler value
        if id(self) in _repr_pydicts:
            return "pydict({...})"
        # Add this object to the set of current repr calls
        _repr_pydicts.add(id(self))
        # A list of parts, to be joined
        parts = []
        # Every part is key: value
        for key, value in self.items():
            parts.append(": ".join([repr(key), repr(value)]))
        # There is no opportunity left for recursion. Therefore, remove
        # this object from the set of current repr calls
        _repr_pydicts.remove(id(self))
        # Join all the parts with ", " add preceeding and suceeding strings.
        # Return the new string.
        return "pydict({" + ", ".join(parts) + "})"    
         
    def __reversed__(self):
        "Return reversed(self)."
        return reversed(self.keys())
    
    def __ror__(self, value):
        "Return value|self"
        return self.__or__(value)
    
    def __setitem__(self, key, value):
        "Set self[key] to value."
        # Resize if necessary (new length will be > threshold)
        threshold = 2 / 3
        if (len(self) + 1)  / (self._size) > threshold:
            _resize_pydict(self, self._size * 2)
        # Get the key's hash code. Trim it to be within the current size.    
        h = hash(key) % self._size
        # Get the absolute value of the trimmed hash code
        h = abs(h)
        # Append to keys, if not already a key
        if key not in self.keys():
            self._keys.append(key)
        # Get the node at the slot in the hash table
        node = self._hash_table[h]
        # If none, make a new corresponding node
        if node is None:
            self._hash_table[h] = _Node(hash(key) % self._size, key, value, None)
        # Otherwise...
        else:
            while True:
                # If there is a corresponding node, update its value
                if node.hashcode == h and node.key == key:
                    node.value = value
                    break
                # If there can't be a corresponding node, chain the 
                # corresponding to the last existing node.
                if node.overflow is None:
                    node.overflow = _Node(hash(key) % self._size, key, value, None)
                    break
                # Continue searching the overflow
                node = node.overflow    
    
    def __sizeof__(self):
        "Size of object in memory, in bytes."
        # Get the raw size of the object
        size = object.__sizeof__(self)
        # Get size of internal keys list. 
        # Its keys aren't private, so don't calculate their sizes
        size += self._keys.__sizeof__()
        # Get size of the internal size counter.
        # TODO: delete the internal size counter and use len(self._hash_table) instead
        size += self._size.__sizeof__()
        # Get the size of internal hash table
        size += self._hash_table.__sizeof__()
        # Get the size of the internal nodes 
        for obj in self._hash_table:
            # Ignore None because None is public
            if isinstance(obj, _Node):
                # Get the size of all the nodes
                size += obj.__sizeof__()
        # That's the size!
        return size
    
    def clear(self):
        "Remove all items from self."
        # Iterate over every key, deleting it.
        for key in self.keys():
            del self[key]
    
    def copy(self):
        "Return a shallow copy of self."
        return self.__class__(self)
    
    @classmethod
    def fromkeys(cls, keys, value=None):
        """
        Create and return a new pydict, p, of type cls.
        For every key in keys, p[key] = value.
        """
        pd = cls()
        pd.update(zip(keys, [value] * len(list(keys))))
        return pd
    
    def get(self, key, default=None):
        """Return self[key] if key in self, else default."""
        try:
            if isinstance(self, defaultpydict):
                if key not in self.keys():
                    return default
            return self[key]
        except KeyError:
            return default
        
    def items(self):
        "Return a view of self's items."
        return PyDictItemView(self)     
                  
    def keys(self):
        "Return a view for self's keys."
        # Return a copy of the internal keys list
        return PyDictKeyView(self)        
        
    def move_to_end(self, key, last=True):
        """Move a key to the back of the pydict.
        If last is False, move the key to the front of the pydict instead.
        Raises KeyError if key not in the pydict.
        """
        # Find the actual key (in case an equivalent was passed in)
        keys = self.keys()
        for i in range(len(keys)):
            if key == keys[i]:
                # Remove the key from my keys list, assign it to the key parameter
                key = self._keys.pop(i)
                break
        else:
            # Raise KeyError if there is no corresponding key
            raise KeyError("Key not in pydict")
        if last:
            # Insert the removed key at the back of my keys list
            self._keys.append(key)
        else:
            # Insert the removed key at the front of my keys list
            self._keys.insert(0, key)
        
    
    def pop(self, key, default=_marker):
        """Remove key from self, return self[key]. 
        If key is not found, return default if given, otherwise raise KeyError."""
        try:
            # Get the value associated with the key
            value = self[key]
            # Delete the key... 
            del self[key]            
        except KeyError:
            # If no default provided when the key isn't present, raise KeyError
            # However, return the default if provided
            if default is _marker:
                raise
            return default
        else:
            #...return its value
            return value
    
    def popitem(self, last=True):
        """Removes a key, return a 2-tuple: (the key, its associated value).
        Removes last key if last is True, otherwise first key.
        Raises KeyError if pydict is empty."""
        # Check if I am empty
        if len(self) == 0:
            raise KeyError("pydict is empty.")
        if last:
            # The key is the last key
            key = self.keys()[-1]
        else:
            # The key is the first key
            key = self.keys()[0]
        # Remove the key. Return (the key, its associated value).
        return key, self.pop(key)
    
    def setdefault(self, key, default=None):
        """Set self[key] to default if key not in pydict.
        Return self[key]."""
        # Set self[key] to default if key not in me
        if key not in self:
            self[key] = default
        # Return self[key]
        return self[key]

    
    def update(self, mapping_or_iterable=(), /, **kwds):
        """p.update(Q, **R)
    Update self from Q and R.
    If Q is present and has a .keys() method, then does:  for k in Q: self[k] = Q[k]
    If Q is present and lacks a .keys() method, then does:  for k, v in Q: self[k] = v
    In either case, this is followed by: for k in R:  self[k] = R[k]
        """
        # Get the value associated with Q's keys attribute.
        # If Q doesn't have a keys attribute, get None instead
        keysfunc = getattr(mapping_or_iterable, "keys", None)
        
        # If the value is callable, it is the keys() method.
        # Call it to get an iterable of Q's keys. Then, for 
        # k in Q's keys, set self[k] to Q[k].
        if callable(keysfunc):
            for key in keysfunc():
                self[key] = mapping_or_iterable[key]
                
        # Otherwise, for k, v in Q, set self[k] to v.
        else:
            for key, value in mapping_or_iterable:
                self[key] = value
        # For k in kwds, set self[k] to kwds[k]
        for key in kwds:
            self[key] = kwds[key]
            
    def values(self):
        "Return a view of self's values."
        # Iterate over the keys. Return the corresponding values.
        return PyDictValueView(self)     

_collections_abc.MutableMapping.register(pydict)

#####################################################
### frozenpydict 
####################################################
    
class frozenpydict(object):
    """Immutable version of pydict
    
    frozenpydict() -> new empty frozen python dictionary
    frozenpydict(mapping) -> new frozen python dictionary initialized from the mapping's (key, value) pairs
    frozenpydict(iterable) -> new frozen python dictionary initialized via:
        frozendict(pydict(iterable))
    frozenpydict(**kwds) -> new frozen python dictionary initialized from the keyword arguments (name, value) pairs
    """
    
    __slots__ = "_keys", "_frozen_hash_table", "_size"
    
    def __new__(cls, mapping_or_iterable=(), /, **kwds):
        # Get a raw object
        self = object.__new__(cls)
        
        # Make a mutable pydict with arguments
        pd = pydict(mapping_or_iterable, **kwds)
        
        # Assign self's attributes, independent but resembling pd's attributes
        self._keys, self._frozen_hash_table, self._size = \
            tuple(pd._keys), tuple(pd._hash_table), pd._size
        
        # No need to obsucre pd, as nobody else may access it.
        # That's it! Return self.
        return self
    
    def __contains__(self, key):
        "Return key in self."
        # Is this object in my keys?
        return key in self.keys()
    
    __class_getitem__ = classmethod(_types.GenericAlias)
    
    def __eq__(self, other):
        "Return self==other"
        # Are self and other the same class? If not, return NotImplemented
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        # Check false with unequal length
        if len(self) != len(other):
            return False
        # Iterate over my keys
        for key in self:
            # If other[key] is absent or unequal to self[key]
            # Return False
            try:
                if self[key] != other[key]:
                    return False
            except KeyError:
                return False
        return True
    
    def __getitem__(self, key):
        "Return self[key]."
        # Get the hash value of the key. Trim it to be within
        # the size (# of buckets available)
        h = hash(key) % self._size
        # Get the result from the hash table.
        result = self._frozen_hash_table[h]
        # If there is no node, raise KeyError
        if result is None:
            raise KeyError(key)
        # Set node to the first node
        node = result
        # Check for the correct node. If so return its value.
        if node.hashcode == h and node.key == key:
            return node.value
        # Search the overflow. Is the a correct node?
        while node.overflow is not None:
            node = node.overflow
            # If so, return its value.
            if node.hashcode == h and node.key == key:
                return node.value
        # There is no corresponding node. Raise KeyError.
        raise KeyError(key)    
    
    def __hash__(self):
        h_items = hash(frozenset(self.items()))
        h = ((h_items << 5) * 31 >> 6) // -7
        if h == -1:
            return 713144892 
        return h
    
    # Avoid subclassing
    __init_subclass__ = None    
    
    def __ior__(self, value):
        "Return self |= value"
        raise TypeError("'|=' not supported by frozenpydict. Use '|' instead.")
    
    def __iter__(self):
        "Return iter(self)"
        # Return the iterator of a copy of this object's keys
        return iter(self.keys())    
    
    def __len__(self):
        "Return len(self)."
        # Return the length of my keys.
        return len(self._keys)
    
    def __ne__(self, other):
        "Return self!=other"
        if not isinstance(other, _collections_abc.Mapping):
            return NotImplemented
        # Return the opposite of self==other
        return not (self == other)
    
    def __or__(self, value):
        "Return self|value"
        pd = pydict(self)
        pd.update(value)
        return frozenpydict(pd)
    
    def __repr__(self):
        "Return repr(self)"
        # If within the midst of another repr call on the same object,
        # return a filler value
        if id(self) in _repr_pydicts:
            return "frozenpydict({...})"
        # Add this object to the set of current repr calls
        _repr_pydicts.add(id(self))
        # A list of parts, to be joined
        parts = []
        # Every part is key: value
        for key, value in self.items():
            parts.append(": ".join([repr(key), repr(value)]))
        # There is no opportunity left for recursion. Therefore, remove
        # this object from the set of current repr calls
        _repr_pydicts.remove(id(self))
        # Join all the parts with ", " add preceeding and suceeding strings.
        # Return the new string.
        return "frozenpydict({" + ", ".join(parts) + "})"    
         
    def __reversed__(self):
        "Return reversed(self)"
        # Return a reverse of my iterator
        return reversed(self.keys())

    def __ror__(self, value):
        "Return value|self"
        return self.__or__(value)
    
    def __sizeof__(self):
        # Get the size of the private internal slots
        size = object.__sizeof__(self)
        size += self._keys.__sizeof__()
        size += self._size.__sizeof__()
        size += self._frozen_hash_table.__sizeof__()
        # Get the size of the internal nodes 
        for obj in self._frozen_hash_table:
            if isinstance(obj, _Node):
                size += obj.__sizeof__()
        # That's the size!
        return size
    
    @classmethod
    def fromkeys(cls, keys, value=None):
        """
        Create and return a new frozenpydict, p.
        For every key in keys, p[key] = value.
        """
        return frozenpydict(zip(keys, [value] * len(list(keys))))
    
    def get(self, key, default=None):
        "Return self[key] if key in self, else default."
        try:
            return self[key]
        except KeyError:
            return default
        
    def items(self):
        "Return a view of self's items."
        return PyDictItemView(self)      
        
    def keys(self):
        "Return a view for self's keys."
        return PyDictKeyView(self)
    
    def values(self):
        "Return a view for self's values."
        return PyDictValueView(self) 

_collections_abc.Mapping.register(frozenpydict)  

#####################################################
### OrderedPyDict 
####################################################    
    
class OrderedPyDict(pydict):
    """Python dictionary that remembers insertion order.
    See help(pydict) for signature of constructor.
    """
    
    def __eq__(self, other):
        "Return self==other"
        if not isinstance(other, OrderedPyDict):
            return NotImplemented
        return tuple(self.items()) == tuple(other.items())
    
    __hash__ = None
    
    def __ne__(self, other):
        "Return self!=other"
        if not isinstance(other, OrderedPyDict):
            return NotImplemented
        return tuple(self.items()) != tuple(other.items())
    
    def __repr__(self):
        "Return repr(self)"
        if len(self) == 0:
            return "OrderedPyDict()"        
        if id(self) in _repr_pydicts:
            return "OrderedPyDict([...])"
        _repr_pydicts.add(id(self))
        parts = []
        for key, value in self.items():
            parts.append(repr((key, value)))
        _repr_pydicts.remove(id(self))
        return "OrderedPyDict([" + ", ".join(parts) + "])"
    
    __slots__ = ()
    
#####################################################
### defaultpydict 
####################################################
    
class defaultpydict(pydict):
    """Python dictionary with an optional default factory when __getitem__ fails due to a KeyError
    
    defaultpydict(default_factory[, ...]) -> new default pydict with its default factory set to default_factory
    
    For other combinations of constructor arguments see help(pydict).
    """
    
    def __missing__(self, key):
        "Fallback method when self[key] fails."
        factory = self.default_factory
        if callable(factory):
            return factory()
        raise KeyError(key)
        
    def __new__(cls, default_factory=None, mapping_or_iterable=(), /, **kwds):
        # Get a raw pydict
        self = pydict.__new__(cls, mapping_or_iterable, **kwds)
        # Assign a default factory
        self.default_factory = default_factory
        # Return self
        return self
    
    def __repr__(self):
        "Return repr(self)"
        if id(self) in _repr_pydicts:
            return "defaultpydict(..., pydict({...}))"
        s = pydict.__repr__(self) 
        _repr_pydicts.add(id(self))
        s = repr(self.default_factory) + ", " + s
        _repr_pydicts.remove(id(self))
        return "defaultpydict(" + s + ")"

    __slots__ = ("_default_factory",)
    
    @property
    def default_factory(self):
        "Factory for default value called by __missing__"
        return getattr(self, "_default_factory", None)
    
    @default_factory.setter
    def default_factory(self, value):
        self._default_factory = value
    
    
    
######################################################
### ShallowChainMap
######################################################
        
class ShallowChainMap(pydict):
    ''' A ShallowChainMap groups multiple pydicts (or other mappings) together
    to create a single, updateable view.

    The underlying mappings are stored in a list.  That list is public and can
    be accessed or updated using the *maps* attribute.  There is no other
    state.

    Lookups search the underlying mappings successively until a key is found.
    In contrast, writes, updates, and deletions only operate on the first
    mapping.
    '''    
    __slots__ = ("_maps",)
    
    def __new__(cls, *maps):
        self = pydict.__new__(cls)
        
        self.maps = list(maps) or [pydict()]
        
        self._keys = self._hash_table = self._size = None
        return self
    
    def __getitem__(self, key):
        for map in self.maps:
            try:
                return map[key]
            except KeyError:
                pass
        return self.__missing__(key)
    
    def __len__(self):
        return sum([len(map) for map in self.maps])
    
    def as_pydict(self):
        "Return self as a plain pydict."
        pd = pydict()
        for map in reversed(self.maps):
            pd.update(map)
        return pd
    
    def __iter__(self):
        return iter(self.as_pydict())
    
    def __reversed__(self):
        return reversed(self.as_pydict())     
    
    def __contains__(self, key):
        return any([key in map for map in self.maps])
    
    def __bool__(self):
        "Return bool(self)."
        return any(self.maps)
    
    def __repr__(self):
        if id(self) in _repr_pydicts:
            return f"{self.__class__.__name__}(...)"
        _repr_pydicts.add(id(self))
        s = f"{self.__class__.__name__}({', '.join([repr(map) for map in self.maps])})"
        _repr_pydicts.remove(id(self))
        return s
    
    
    def copy(self):
        "Return a new ShallowChainMap or subclass. \nIts first map is copied, while other mappings remain intact."
        return self.__class__(self.maps[0].copy(), *self.maps[1:])
    
    @property
    def maps(self):
        "A mutable list of this ShallowChainMap's maps"
        if not hasattr(self, '_maps'):
            self._maps = [pydict()]
        return self._maps
            
    @maps.setter
    def maps(self, value):
        value = list(value)
        if not value:
            self._maps = [pydict()]
            return
        for item in value:
            if not isinstance(item, _collections_abc.Mapping):
                raise TypeError(f"All items of maps list must be instances of collections.abc.Mapping, " + \
                f"not {item.__class__.__module__}.{item.__class__.__name__}")
        self._maps = value
        
    def child(self, map=None):
        "Return PyChainMap(map, *self.maps). \nIf map not given, it defaults to an empty pydict."
        if map is None:
            map = pydict()
        return self.__class__(map, *self.maps)
    
    @property
    def parent(self):
        "Returns PyChainMap(*self.maps[1:])"
        return self.__class__(*self.maps[1:])
    
    def __setitem__(self, key, value):
        self.maps[0][key] = value
        
    def __delitem__(self, key):
        try:
            del self.maps[0][key]
        except KeyError:
            raise KeyError(f"{key} not found in the first mapping.")
        
    def __sizeof__(self):
        # _keys, _hash_table, and _size are None
        # _maps list can be accessed through maps property
        # Therefore, no private internals to be accounted for
        return object.__sizeof__(self)
        
    def popitem(self, last=True):
        """Removes a key from the first mapping, return a 2-tuple: (the key, its associated value).
        Raises KeyError if the first mapping is empty.
        
        By default, the last key is removed.
        When the first mapping's popitem supports the last argument, if bool(last)
        evaluates to False, the first key is removed instead."""        
        try:
            try:
                return self.maps[0].popitem(last)
            except TypeError:
                return self.maps[0].popitem()
        except KeyError:
            raise KeyError("first mapping is empty.")
        
    def clear(self):
        "Clear the first mapping."
        self.maps[0].clear()
    
    def keys(self):
        return self.as_pydict().keys()
    
    def values(self):
        return self.as_pydict().values()
    
    def items(self):
        return self.as_pydict().items()
    
    
##################################
### DeepChainMap
##################################
    
class DeepChainMap(ShallowChainMap):
    """A ShallowChainMap where writes, updates, and deletions operate
    on all mappings, not just the first."""
    def copy(self):
        "Create a new DeepChainMap, with all maps copied."
        c = []
        for map in self.maps:
            try:
                c.append(map.copy())
            except AttributeError:
                c.append(map)
        return DeepChainMap(*c)
    
    def clear(self):
        "Clear all mappings."
        for map in self.maps:
            try:
                map.clear()
            except Exception:
                pass
        
    
    def popitem(self, last=True):
        """Removes a key from the first non-empty mapping, return a 2-tuple: (the key, its associated value).
        Raises KeyError if all mappings are empty.
        
        By default, the last key is removed.
        When the first non-empty mapping's popitem supports the last argument, if bool(last)
        evaluates to False, the first key is removed instead."""

        for map in self.maps:
            try:
                try:
                    return map.popitem(last)
                except TypeError:
                    return map.popitem()    
            except KeyError:
                pass
        raise KeyError(key)
    
    def __delitem__(self, value):
        for map in self.maps:
            try:
                del map[value]
                return
            except KeyError:
                pass
        raise KeyError(key)
    
    def __setitem__(self, key, value):
        for mapping in self.maps:
            if key in mapping:
                mapping[key] = value
                return
        self.maps[0][key] = value    
    
    __slots__ = ()    
    
                    
    
##################################
### Final touches, testing
##################################
__all__ = [i for i in globals() if i[0] != "_"]



##########################################
### End important part of module
###########################################


# Views and iterators. No need to export.
####################################################
### views
####################################################

class PyDictView(object):
    def __contains__(self, key):
        "Return key in self."
        return key in list(self)
    
    def __iter__(self):
        "Return iter(self)."
        return PyDictIterator(self._mapping)
    
    def __len__(self):
        "Return len(self)."
        return len(self._mapping)
    
    def __new__(cls, mapping=None):
        if _sys._getframe(1).f_globals is not globals():
            raise TypeError(f"Cannot create {cls.__name__} instances")        
        self = object.__new__(cls)
        self._mapping = mapping
        return self
    
    def __repr__(self):
        "Return repr(self)."
        return f"{self.__class__.__name__}({list(self)})"
    
    def __reversed__(self):
        "Return reversed(self)."
        return PyDictReverseIterator(self._mapping)
    
    __slots__ = ('_mapping',)
    
    @property
    def mapping(self):
        "Return a read-only version of the original pydict/frozenpydict."
        if isinstance(self._mapping, frozenpydict):
            return self._mapping
        return frozenpydict(self._mapping)
    
class PyDictSetView(PyDictView):
    "Base class of PyDictViews which implements some set functionality."
    
    def __and__(self, other):
        "Return self&other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return {i for i in self if i in other}
    
    def __eq__(self, other):
        "Return self==other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return self <= other and len(self) == len(other)
    
    def __ge__(self, other):
        "Return self>=other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented
        for item in other:
            if item not in self:
                return False
        return True
    
    def __gt__(self, other):
        "Return self>other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return self >= other and len(self) > len(other)
    
    __hash__ = None
    
    def __le__(self, other):
        "Return self<=other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented
        for item in self:
            if item not in other:
                return False
        return True

    def __lt__(self, other):
        "Return self<other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return self <= other and len(self) < len(other)
    
    def __ne__(self, other):
        "Return self!=other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented
        return not (self == other)
    
    def __or__(self, other):
        "Return self|other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return {value for value in [*self, *other]}

    def __rand__(self, other):
        "Return other&self"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented       
        return self.__and__(other)
    
    def __ror__(self, other):
        "Return other|self"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return self.__or__(other)
    
    def __rsub__(self, other):
        "Return other-self"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return {i for i in other if i not in self}
    
    def __rxor__(self, other):
        "Return other^self"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return self.__xor__(other)
    
    __slots__ = ()
    
    def __sub__(self, other):
        "Return self-other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return {i for i in self if i not in other}
    
    def __xor__(self, other):
        "Return self^other"
        if not isinstance(other, _collections_abc.Iterable):
            return NotImplemented        
        return (self | other) - (self & other)
    
    def isdisjoint(self, other):
        "Return if self and other have a null intersection."
        if not isinstance(other, _collections_abc.Iterable):
            raise TypeError("other arg must be iterable")
        return (self & other) == set()
    
    
class PyDictKeyView(PyDictSetView):
    "View for the keys of a pydict/frozenpydict"
    def __iter__(self):
        return PyDictKeyIterator(self._mapping)
    
    def __reversed__(self):
        return PyDictReverseKeyIterator(self._mapping)
    
    __slots__ = ()
    
class PyDictValueView(PyDictView):
    "View for the values of a pydict/frozenpydict"
    def __iter__(self):
        return PyDictValueIterator(self._mapping)  
    
    def __reversed__(self):
        return PyDictReverseValueIterator(self._mapping)    
    
    __slots__ = ()
    
class PyDictItemView(PyDictSetView):
    "View for the items of a pydict/frozenpydict"
    def __iter__(self):
        return PyDictItemIterator(self._mapping)
    
    def __reversed__(self):
        return PyDictReverseItemIterator(self._mapping)    
    
    __slots__ = ()
    
####################################################
### iterators
####################################################

class PyDictIterator(object):
    "Base class for iterators of pydicts and frozenpydicts"
    
    def __iter__(self):
        "Return iter(self)."
        return self
    
    def __next__(self):
        "Return next(self)."
        raise StopIteration
    
    def __new__(cls, mapping=None):
        if _sys._getframe(1).f_globals is not globals():
            raise TypeError(f"Cannot create {cls.__name__} instances")
        self = object.__new__(cls)
        self._count = -1
        self._mapping = mapping
        self._length = len(self._mapping)
        return self
    
    __slots__ = ("_count", "_length", "_mapping")

class PyDictKeyIterator(PyDictIterator):
    "Iterator for the keys of a pydict/frozenpydict"
    
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")
        try:
            self._count += 1
            return self._mapping._keys[self._count]
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
class PyDictValueIterator(PyDictIterator):
    "Iterator for the values of a pydict/frozenpydict"
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")        
        try:
            self._count += 1
            return self._mapping[self._mapping._keys[self._count]]
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
class PyDictItemIterator(PyDictIterator):
    "Iterator for the items of a pydict/frozenpydict"
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")        
        try:
            self._count += 1
            return (self._mapping._keys[self._count], 
                    self._mapping[self._mapping._keys[self._count]])
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
####################################################
### reverse iterators
####################################################

class PyDictReverseIterator(PyDictIterator):
    "Base class for reverse iterators of pydicts and frozenpydicts"
    
    def __new__(cls, mapping=None):
        self = PyDictIterator.__new__(cls, mapping)
        self._count = 0
        return self
    
    __slots__ = ()
    
class PyDictReverseKeyIterator(PyDictReverseIterator, PyDictKeyIterator):
    "Reverse iterator for the keys of a pydict/frozenpydict"
    
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")
        try:
            self._count -= 1
            return self._mapping._keys[self._count]
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
class PyDictReverseValueIterator(PyDictReverseIterator, PyDictValueIterator):
    "Reverse iterator for the values of a pydict/frozenpydict"
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")        
        try:
            self._count -= 1
            return self._mapping[self._mapping._keys[self._count]]
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
class PyDictReverseItemIterator(PyDictReverseIterator, PyDictItemIterator):
    "Reverse iterator for the items of a pydict/frozenpydict"
    def __next__(self):
        if len(self._mapping) != self._length:
            raise RuntimeError("iterable changed size during iteration")        
        try:
            self._count -= 1
            return (self._mapping._keys[self._count], 
                    self._mapping[self._mapping._keys[self._count]])
        except IndexError:
            pass
        raise StopIteration
        
    __slots__ = ()
    
# Register classes
_collections_abc.Collection.register(PyDictView)
_collections_abc.MappingView.register(PyDictView)
_collections_abc.Set.register(PyDictSetView)
_collections_abc.KeysView.register(PyDictKeyView)
_collections_abc.ItemsView.register(PyDictItemView)
_collections_abc.ValuesView.register(PyDictValueView)
_collections_abc.Iterator.register(PyDictIterator)