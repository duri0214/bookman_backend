from bookman.models import Branch, BranchClosedDay


class BranchClosedDayRepository:
    """
    支店休館日の永続化操作。
    """

    def get_by_branch_and_date(
        self,
        *,
        branch: Branch,
        closed_date,
    ) -> BranchClosedDay | None:
        """
        指定支店の指定日が休館日として登録されていれば返す。
        """
        try:
            return BranchClosedDay.objects.get(branch=branch, date=closed_date)
        except BranchClosedDay.DoesNotExist:
            return None
