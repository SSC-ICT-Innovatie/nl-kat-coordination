import json
import os
import unittest

from scheduler.storage.filters import Filter, FilterRequest, apply_filter
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class TestModel(Base):
    __tablename__ = "test"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    height = Column(Float)
    is_active = Column(Boolean)
    data = Column(JSONB, nullable=False)

    children = relationship("TestModelChild", back_populates="parent")


class TestModelChild(Base):
    __tablename__ = "test_child"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    height = Column(Float)
    is_active = Column(Boolean)
    data = Column(JSONB, nullable=False)

    parent_id = Column(Integer, ForeignKey("test.id", ondelete="SET NULL"))
    parent = relationship("TestModel", back_populates="children")


# Database setup
engine = create_engine(f"{os.getenv('SCHEDULER_DB_URI')}")
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


class FilteringTestCase(unittest.TestCase):
    def setUp(self):
        alice = TestModel(
            name="Alice",
            age=25,
            height=1.8,
            is_active=True,
            data={"foo": "bar", "score": 15, "nested": {"bar": "baz"}, "list": ["ipv4", "network/local"]},
        )
        bob = TestModel(
            name="Bob",
            age=30,
            height=1.7,
            is_active=False,
            data={"foo": "baz", "score": 25, "nested": {"bar": "baz"}, "list": ["ipv4", "ipv6", "network/local"]},
        )
        charlie = TestModel(
            name="Charlie",
            age=28,
            height=1.6,
            is_active=True,
            data={"foo": "bar", "score": 35, "nested": {"bar": "baz"}, "list": ["ipv4", "ipv6", "network/internet"]},
        )

        session.add_all([alice, bob, charlie])

        # Get ids
        session.flush()

        david = TestModelChild(
            name="David",
            age=12,
            height=1.2,
            is_active=True,
            data={"foo": "bar", "score": 45, "nested": {"bar": "baz"}},
            parent_id=alice.id,
        )

        erin = TestModelChild(
            name="Erin",
            age=6,
            height=1.3,
            is_active=True,
            data={"foo": "baz", "score": 55, "nested": {"bar": "baz"}},
            parent_id=alice.id,
        )

        session.add_all([david, erin])

        self.models = {"alice": alice, "bob": bob, "charlie": charlie, "david": david, "erin": erin}

        session.commit()

    def tearDown(self):
        session.query(TestModel).delete()
        session.commit()

    def test_apply_filter_basic(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="name", operator="eq", value="Alice"),
                    Filter(column="age", operator="eq", value=25),
                    Filter(column="height", operator="eq", value=1.8),
                    Filter(column="is_active", operator="eq", value=True),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_nested_fields(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="name", operator="eq", value="Alice"),
                    Filter(column="data", field="foo", operator="eq", value="bar"),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_casting(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="name", operator="eq", value="Alice"),
                    Filter(column="age", operator="eq", value="25"),
                    Filter(column="height", operator="eq", value="1.8"),
                    Filter(column="is_active", operator="eq", value="True"),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_empty_filter_request(self):
        filter_request = FilterRequest(filters={})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 3)

    def test_apply_filter_or(self):
        filter_request = FilterRequest(
            filters={
                "or": [
                    Filter(column="name", operator="eq", value="Alice"),
                    Filter(column="name", operator="eq", value="Bob"),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Bob")

    def test_apply_filter_and(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="name", operator="eq", value="Alice"),
                    Filter(column="age", operator="eq", value=25),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_not(self):
        filter_request = FilterRequest(filters={"not": [Filter(column="name", operator="eq", value="Alice")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Bob")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_numeric(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="age", operator="gt", value=25),
                    Filter(column="height", operator="lt", value=1.7),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Charlie")

    def test_apply_filter_string(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="name", operator="like", value="A%"),
                    Filter(column="name", operator="like", value="%ce"),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_boolean(self):
        filter_request = FilterRequest(
            filters={
                "and": [
                    Filter(column="is_active", operator="==", value=True),
                    Filter(column="is_active", operator="!=", value=False),
                ]
            }
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_eq(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="eq", value="Alice")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="==", value="Alice")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_json_eq(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="eq", value="bar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Charlie")

        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="==", value="bar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_ne(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="ne", value="Alice")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Bob")
        self.assertEqual(results[1].name, "Charlie")

        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="!=", value="Alice")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Bob")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_json_ne(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="ne", value="bar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="!=", value="bar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_is(self):
        filter_request = FilterRequest(filters=[Filter(column="is_active", operator="is", value=True)])

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_is_not(self):
        filter_request = FilterRequest(filters=[Filter(column="is_active", operator="is_not", value=True)])

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertIn("Bob", [r.name for r in results])

    def test_apply_filter_gt(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="gt", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator=">", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_json_gt(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator="gt", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Charlie")

        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator=">", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Charlie")

    def test_apply_filter_gte(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="gte", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 3)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator=">=", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 3)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_json_gte(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="score", operator="gte", value=25)]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator=">=", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertIn("Bob", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_lt(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="lt", value=28)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="<", value=28)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_json_lt(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator="lt", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator="<", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_lte(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="lte", value=28)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

        filter_request = FilterRequest(filters={"and": [Filter(column="age", operator="<=", value=28)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.age).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_json_lte(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="score", operator="lte", value=25)]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Bob", [r.name for r in results])

        filter_request = FilterRequest(filters={"and": [Filter(column="data", field="score", operator="<=", value=25)]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Bob", [r.name for r in results])

    def test_apply_filter_like(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="like", value="B%")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_json_like(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="like", value="%ar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_not_like(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="not_like", value="B%")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_json_not_like(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="not_like", value="%ar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_ilike(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="ilike", value="B%")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_json_ilike(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="ilike", value="%AR")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_not_ilike(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="not_ilike", value="B%")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_json_not_ilike(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="not_ilike", value="%AR")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_in(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="in", value=["Alice", "Bob"])]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Bob")

    def test_apply_filter_json_in(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="in", value=["bar", "baz"])]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 3)

    def test_apply_filter_not_in(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="name", operator="not_in", value=["Alice", "Bob"])]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Charlie")

    def test_apply_filter_json_not_in(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="not_in", value=["bar"])]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bob")

    def test_apply_filter_contains(self):
        filter_request = FilterRequest(filters={"and": [Filter(column="name", operator="contains", value="li")]})

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_json_contains(self):
        filter_request = FilterRequest(
            filters={"and": [Filter(column="data", field="foo", operator="contains", value="ar")]}
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 2)
        self.assertIn("Alice", [r.name for r in results])
        self.assertIn("Charlie", [r.name for r in results])

    def test_apply_filter_jsonb_contains(self):
        filter_request = FilterRequest(filters=[Filter(column="data", operator="@>", value=json.dumps({"foo": "bar"}))])

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Charlie")

    def test_apply_filter_jsonb_contains_list(self):
        filter_request = FilterRequest(
            filters=[Filter(column="data", field="list", operator="@>", value=json.dumps(["ipv4"]))]
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Bob")
        self.assertEqual(results[2].name, "Charlie")

    def test_apply_filter_jsonb_contained_by_list(self):
        filter_request = FilterRequest(
            filters=[
                Filter(column="data", field="list", operator="<@", value=json.dumps(["ipv4", "ipv6", "network/local"]))
            ]
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.order_by(TestModel.name).all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "Alice")
        self.assertEqual(results[1].name, "Bob")

    def test_apply_filter_related(self):
        filter_request = FilterRequest(
            filters=[Filter(column="parent", field="name", operator="eq", value=self.models.get("alice").name)]
        )

        query = session.query(TestModelChild)
        filtered_query = apply_filter(TestModelChild, query, filter_request)

        results = filtered_query.order_by(TestModelChild.name).all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "David")
        self.assertEqual(results[1].name, "Erin")

    def test_apply_filter_related_reversed(self):
        filter_request = FilterRequest(
            filters=[Filter(column="children", field="name", operator="eq", value=self.models.get("david").name)]
        )
        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_related_and_nested__(self):
        filter_request = FilterRequest(
            filters=[Filter(column="children", field="data__foo", operator="eq", value="bar")]
        )

        query = session.query(TestModel)
        filtered_query = apply_filter(TestModel, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    def test_apply_filter_related_and_nested_reversed(self):
        filter_request = FilterRequest(filters=[Filter(column="parent", field="data__foo", operator="eq", value="bar")])

        query = session.query(TestModelChild)
        filtered_query = apply_filter(TestModelChild, query, filter_request)

        results = filtered_query.all()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "David")
        self.assertEqual(results[1].name, "Erin")
