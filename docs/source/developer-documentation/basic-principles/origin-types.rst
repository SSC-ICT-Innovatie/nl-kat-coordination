.. _basics-origin-types:

Origin types
============

Each object in OpenKAT has an origin. An origin connects an object, such as a hostname, to the objects produced by a task that used this object as an input, such as a dns-scan.
The produced objects are called the origin's "output", and we say that each object in the output is "proven" by its origin.
In OpenKAT, each valid object should therefore be in at least (the output of) one origin: else, it is no longer proven.
Equivalently, each valid origin should have a proven input object: origins for which the input has disappeared are themselves no longer proven.
Objects and origins that are no longer proven should be deleted.
This is the basis of our garbage collection process that we call "deletion propagation": deleting an object could trigger the deletion of multiple origins, which in turn could trigger the deletion of multiple objects, etc.

There are 4 different origin types depending on how the origin was created and how deletion propagation should treat it:

* **Observation**: observations are made by a (boefje and) normalizer. By definition, observed objects are proved as long as their input object of their observation exists.
* **Inference**: inferences are like observations objects, but come from bits or nibbles: bits and nibbles only query additional information from our own object database and are therefore "pure" operations on an object database. Inferencing should in real-time.
* **Declaration**: declaration "circular" origins: an origin where the output is its input object. As a consequence, both the declaration and input/output object are not targeted by deletion propagation and can only be removed manually. Therefore, objects added manually by users are declared objects. These are often hostnames, URLs or IP-addresses the user wants to use as a starting point for scans by boefjes.
* **Affirmation**: affirmed objects provide additional information about an object, but don't prove its existence. This is the case when one boefje/normalizer finds CVE findings, and another boefje imports a large dataset of fresh CVE information (description and score) that needs to be added to the CVE Findings. If the observation for the CVE object disappears (e.g. the CVE is resolved), the affirmation should obviously not prevent the removal of the CVE object.

To conclude, deletion propagation could be summarized as:

1. When an object is deleted, delete all origins that has this object as input.
2. When an origin is deleted, delete all objects in its output that do not have another origin that is not an Affirmation.

These two steps form a recursive algorithm that terminates even when the object database has a cycle (a chain of objects and origins, or "path", where the original object appears in the output of the last origin), because after step 1 the deleted object is also removed from all origin outputs.

Still, it is theoretically possible that a cycle exists where none of the objects has a path back to a declared object.
Although we are considering solutions to tackle this edge-case with more sophisticated deletion propagation, in practice these instances are rare and often easily solved by deleting one of the objects in the cycle manually.
