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

      frappe.log_error(f'Function failed: {func.__name__}')

      # Propagate the exception after logging, you can optionally add:
      raise

  return wrapper
