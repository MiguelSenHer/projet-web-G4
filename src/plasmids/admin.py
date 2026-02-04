from django.contrib import admin
from .models import Collection, Plasmid, MappingTable, MappingCollection

admin.site.register(Collection)
admin.site.register(Plasmid)
admin.site.register(MappingCollection)
admin.site.register(MappingTable)