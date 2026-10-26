-- Infrastructure-only singular test: succeeds when SQL returns zero failures.
select 1 as failure where 1 != 1
