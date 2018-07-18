import re
import ast
import json

class Result():
    def __init__(self, result):
        self.result = result

    def count(self):
        return len(self.result)

    def sort(self, sort_key, sort_order):
        # sort_key = "_id"
        # sort_order = 1 or -1
        return Result(sorted(
            self.result,
            key=lambda row: get_item_in_dict(self.result, sort_key),
            reverse=sort_order == -1))

    def __getitem__(self, item):
        return self.result[item]

    def __len__(self):
        return len(self.result)

    def __str__(self):
        return str(self.result)

    def __repr__(self):
        return repr(self.result)

class Table():
    """
    Base table class.
    """
    def __init__(self, database=None, name=None):
        self.database = database
        self.name = name

def get_item_in_dict(dictionary, item):
    """
    Get dictionary item from a dotted-word.

    >>> get_item_in_dict({"x": 1}, "x")
    1
    >>> get_item_in_dict({"x": {"y": 42}}, "x.y")
    42
    """
    current = dictionary
    for word in item.split("."):
        if word in current:
            current = current[word]
        else:
            return None
    return current

def set_item_in_dict(dictionary, item, value):
    """
    Set dictionary item from a dotted-word.

    >>> d = {"x": 1}
    >>> get_item_in_dict(d, "x")
    1
    >>> set_item_in_dict(d, "x", 2)
    >>> get_item_in_dict(d, "x")
    2
    >>> d2 = {"x": {"y": 42}}
    >>> get_item_in_dict(d2, "x.y")
    42
    >>> set_item_in_dict(d2, "x.y", 43)
    >>> get_item_in_dict(d2, "x.y")
    43
    """
    current = dictionary
    words = item.split(".")
    for word in words[:-1]:
        current = current[word]
    current[words[-1]] = value

def is_match(lhs, rhs):
    """
    >>> is_match(12, 12)
    True
    >>> is_match(12, 13)
    False
    >>> is_match(12, {"$lt": 11})
    True
    >>> is_match(12, {"$lt": 13})
    False
    >>> is_match({"a1": 1, "a2": 2, "b3": 3}, {"$regex": "^a"})
    True
    >>> is_match({"a1": 1, "a2": 2, "b3": 3}, {"$regex": "^b"})
    True
    >>> is_match({"a1": 1, "a2": 2, "b3": 3}, {"$regex": "^c"})
    False
    """
    if isinstance(rhs, dict):
        matched = True
        for item in rhs:
            if item == "$regex":
                matched = any([key for key in lhs if re.match(rhs[item], key)])
            elif item == "$lt":
                matched = rhs[item] < lhs
            elif item == "$gt":
                matched = rhs[item] > lhs
            else:
                raise Exception("unknown operator: %s" % item)
            if not matched:
                return False
        return matched
    else:
        return lhs == rhs
    
def match(doc, query):
    """
    Does a dictionary match a (possibly-nested) query/dict?

    query is a dictionary of dotted words or query operations.

    >>> match({"x": 42}, {"x": 42})
    True
    >>> match({"x": 42}, {"x": 43})
    False
    >>> match({"x": {"y": 5}}, {"x.y": 5})
    True
    >>> match({"x": {"y": 5}}, {"x.y": 4})
    False
    >>> activity = {"name": "Joe"}
    >>> match(activity, {"$and": [{"name": "Sally"}, {"name": "Joe"}]})
    False
    >>> match(activity, {"$and": [{"name": "Joe"}, {"name": "Sally"}]})
    False
    >>> match(activity, {"$or": [{"name": "Sally"}, {"name": "Joe"}]})
    True
    >>> match(activity, {"$or": [{"name": "Joe"}, {"name": "Sally"}]})
    True
    """
    for item in query:
        if item == "$or":
            matched = False
            for each in query[item]:
                if match(doc, each):
                    matched = True
                    break
            if not matched:
                return False
        elif item == "$and":
            matched = True
            for each in query[item]:
                if not match(doc, each):
                    matched = False
                    break
            if not matched:
                return False
        else:
            thing = get_item_in_dict(doc, item)
            matched = is_match(thing, query[item])
            if not matched:
                return False
    return True
        
class ListTable(Table):
    ID = 1
    def __init__(self, database=None, name=None):
        super().__init__(database, name)
        self.data = []

    def drop(self):
        self.data = []

    def insert_one(self, row):
        """
        >>> table = ListTable()
        >>> table.count()
        0
        >>> len(table.data)
        0
        >>> table.insert_one({"a": 1, "b": 2})
        >>> len(table.data)
        1
        >>> table.count()
        1
        >>> table.insert_one({"c": 1, "d": 2})
        >>> table.insert_one({"c": 1, "d": 2})
        >>> table.insert_one({"c": 1, "d": 3})
        >>> table.insert_one({"c": 1, "d": 3})
        >>> table.find({"a": 1}).count()
        1
        >>> table.find({"a": 2}).count()
        0
        >>> table.find({"b": 2}).count()
        1
        >>> table.find({"c": 1}).count()
        4
        >>> table.find({"c": 1, "d": 2}).count()
        2
        """
        row["_id"] = self.ID
        self.ID += 1
        self.data.append(row)

    def find(self, query=None):
        """
        >>> table = ListTable()
        >>> table.insert_one({"a": 1, "b": 2})
        >>> table.find({"a": 1})
        [{'a': 1, 'b': 2, '_id': 1}]
        >>> table.find({"a": 2})
        []
        """
        if query:
            return Result([doc for doc in self.data if match(doc, query)])
        else:
            return Result(self.data)

    def remove(self, query=None):
        """
        >>> table = ListTable()
        >>> table.insert_one({"a": 1, "b": 2})
        >>> table.insert_one({"c": 3, "d": 4})
        >>> table.find({"a": 1})
        [{'a': 1, 'b': 2, '_id': 1}]
        >>> table.find({"a": 2})
        []
        >>> table.find({"d": 4})
        [{'c': 3, 'd': 4, '_id': 2}]
        """
        if query:
            items = [doc for doc in self.data if match(doc, query)]
            # delete them
        else:
            self.data = []

    def find_one(self, query):
        results = [doc for doc in self.data if match(doc, query)]
        if results:
            return results[0]
        else:
            return None

    def find_one_and_update(self, query, items, sort=None):
        one = self.find_one(query)
        if len(one) > 0:
            return False
        else:
            self.update_one(query, items)
            return True

    def update_one(self, query, items, upsert=False):
        results = [doc for doc in self.data if match(doc, query)]
        for result in results:
            for item in items:
                pass
                #if item == "$set":
                #elif item == "$inc": 

    def count(self, query=None):
        if query:
            return len([doc for doc in self.data if match(doc, query)])
        else:
            return len(self.data)

class Database():
    def __init__(self, Table):
        self.activities = Table(self, "activities")
        self.u2f = Table(self, "u2f")
        self.instances = Table(self, "instances")
        self.actors = Table(self, "actors")
        self.indieauth = Table(self, "indieauth")

class ListDatabase(Database):
    def __init__(self):
        super().__init__(ListTable)
