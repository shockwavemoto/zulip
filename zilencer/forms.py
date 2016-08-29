from django import forms

class EnterpriseToSForm(forms.Form):
    full_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=100)
    terms = forms.BooleanField(required=True)
    
class RemoveUnminifiedFilesMixin(object):
    def post_process(self, paths, dry_run=False, **kwargs):
        # type: (Dict[str, Tuple[ZulipStorage, str]], bool, **Any) -> List[Tuple[str, str, bool]]
        if dry_run:
            return []

        root = settings.STATIC_ROOT
        to_remove = ['templates', 'styles', 'js']

        for tree in to_remove:
            shutil.rmtree(os.path.join(root, tree))

        is_valid = lambda p: all([not p.startswith(k) for k in to_remove])

        paths = {k: v for k, v in paths.items() if is_valid(k)}
        super_class = super(RemoveUnminifiedFilesMixin, self)  # type: ignore # https://github.com/JukkaL/mypy/issues/857
        if hasattr(super_class, 'post_process'):
            return super_class.post_process(paths, dry_run, **kwargs)

        return []


class ZulipStorage(PipelineMixin,
        AddHeaderMixin, RemoveUnminifiedFilesMixin,
        CachedFilesMixin, StaticFilesStorage):
    pass

