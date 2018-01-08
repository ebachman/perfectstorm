Triggers
========

Triggers can be used to perform actions on `groups </groups>`. Triggers are submitted as a name, that identifies the
type of the trigger, and a series of arguments (a JSON document). Once the user submits a trigger, a process capable of
executing that type of trigger will be notified and will perform an operation. Once the execution has completed, a JSON
object will be added to it as the result of the operation.

Triggers are stored by the API server into the database. The API server is designed to allow safe concurrent handling
of triggers: trigger executors can be distributed and can scale however they want.


Usage
-----

A trigger can be sent with this command::

    stormctl trigger -n TRIGGER_NAME

Arguments can be provided into a YAML file using the ``-f`` option::

    stormctl trigger -n TRIGGER_NAME -f arguments.yaml


Workflow
--------

When a trigger is submitted, its initial status is `pending`. Trigger executors that know how to handle certain type
of triggers will query for those in `pending` status and mark them as `running` as they are operating on them.

The transition from `pending` status to `running` is done using the API endpoint ``/v1/triggers/$ID/handle/``. This
endpoint ensures that only one executor can mark a trigger as `running` at the same time: if two or more executors
call ``/v1/triggers/$ID/handle/`` at the same time, only one of them will succeed.

After an executor has successfully marked the trigger has `running`, it will perform the necessary operations to
complete the request. When it finishes, it can mark the trigger as `done` and optionally set the `result` attribute
of the trigger.

If an error occurs, an executor can mark the trigger as being in `error` status. The `result` attribute will contain
details about what went wrong.


Heartbeat
---------

One important question regarding the workflow is: if an executor marks a trigger as `running` and then dies before
completion, who will take care of re-trying the trigger? To solve this problem, triggers offer the concept of
heartbeat: executors are supposed to call ``/v1/triggers/$ID/heartbeat/`` periodically to signal that they are still
alive and operating normally.

If a trigger is in status `running` and a heartbeat has not been received within 60 seconds, it will be considered
stale and will be transitioned back to the `pending` status, so that another executor will have the chance to take
care of it.

The recommended frequency for heartbeat is 30 seconds, i.e. half of the timeout.
