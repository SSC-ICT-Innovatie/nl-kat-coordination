.. _basics-bits:

Bits
====

Bits are businessrules that assess objects. These can be disabled or enabled using environment variables. The parameters of a Bit can be configured using config objects, which are explained in detail in :ref:`make-your-own-bits`.

Almost all bits are enabled by default and be disabled by adding the bit to `BITS_DISABLED`. The disabled bits can be enabled using `BITS_ENABLED`. For example:

.. code-block:: sh

    BITS_ENABLED='["bit1","bit2"]'
    BITS_DISABLED='["bit3"]'


Note that if you enable a bit that was previously enabled the bit won't be automatically run for every object it should have run on, but only when it is triggered again after a new scan or other bit that has run. When a bit that was previously enabled is disabled the resulting objects from that bit will also not be automatically removed. Only when the bit triggers instead of running the bit the resulting OOIs of the previous run will be deleted. This also means that if the bit isn't triggered the old objects will not be removed.
