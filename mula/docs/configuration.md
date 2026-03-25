# Configuration

The scheduler allows some configuration options to be set. Environment
variables are used to configure the scheduler. And these can be set in the
`.env-dist` file. When a value isn't set the default value from the scheduler
will be used. Check the [`settings.py`](../scheduler/config/settings.py) file
for the default values and what value you can set.

## Setting scheduler configuration values

To set the configuration values, you can set the environment variables by
checking the `settings.py` and prepending `SCHEDULER_` to the variable
names. For example, if you want to set the `SCHEDULER_DEBUG` to `True`, you
can add the following line to your `.env` file:

```env
SCHEDULER_DEBUG=True
```
