import pydict
for key in dir(pydict):
    if "Iterator" in key:
        eval(f"{key} = pydict.{key}")
        eval(f"{key}.__module__ = 'iterators'")