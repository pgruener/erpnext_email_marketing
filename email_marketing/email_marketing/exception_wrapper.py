import functools
import frappe

def exception_handler_decorator(func):
  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    try:
      result = func(*args, **kwargs)

      return result

    except Exception:
      frappe.db.rollback()

      # Convert args and kwargs to a string representation
      args_repr = ', '.join(repr(a) for a in args)
      kwargs_repr = ', '.join(f'{k}={v!r}' for k, v in kwargs.items())
      serialized_args = f'args: ({args_repr}), kwargs: ({kwargs_repr})'

      frappe.logger().error(f'Function failed: {func.__name__}\n{serialized_args}', exc_info=True)

      # Propagate the exception after logging, you can optionally add:
      raise

  return wrapper
