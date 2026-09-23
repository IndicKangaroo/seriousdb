{{ fullname | escape | underline }}

.. automodule:: {{ fullname }}

   {% block functions -%}
   {%- if functions %}
   .. rubric:: Functions

   {% for item in functions %}
   .. autofunction:: {{ item }}
   {% endfor -%}
   {%- endif -%}
   {%- endblock %}

   {% block classes -%}
   {%- if classes %}
   .. rubric:: Classes

   {% for item in classes %}
   .. autoclass:: {{ item }}
      :members:
      :undoc-members:
      :show-inheritance:
   {% endfor -%}
   {%- endif -%}
   {%- endblock %}

   {% block exceptions -%}
   {%- if exceptions %}
   .. rubric:: Exceptions

   {% for item in exceptions %}
   .. autoexception:: {{ item }}
   {% endfor -%}
   {%- endif -%}
   {%- endblock %}

   {% block attributes -%}
   {%- if attributes %}
   .. rubric:: Module attributes

   {% for item in attributes %}
   .. autodata:: {{ item }}
   {% endfor -%}
   {%- endif -%}
   {%- endblock %}
