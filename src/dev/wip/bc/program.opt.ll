; ModuleID = 'dev/wip/bc/program.opt.bc'
source_filename = "dev/working/samples/add4.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@A = dso_local global i32 5, align 4
@B = dso_local global i32 7, align 4
@Cc = dso_local global i32 11, align 4
@Dd = dso_local global i32 13, align 4

; Function Attrs: mustprogress nofree norecurse nounwind willreturn memory(readwrite, argmem: none)
define dso_local i32 @main() local_unnamed_addr #0 {
  %1 = load volatile i32, ptr @A, align 4, !tbaa !4
  %2 = load volatile i32, ptr @B, align 4, !tbaa !4
  %3 = load volatile i32, ptr @Cc, align 4, !tbaa !4
  %4 = load volatile i32, ptr @Dd, align 4, !tbaa !4
  %5 = add nsw i32 %2, %1
  %6 = add nsw i32 %5, %3
  %7 = add nsw i32 %6, %4
  ret i32 %7
}

attributes #0 = { mustprogress nofree norecurse nounwind willreturn memory(readwrite, argmem: none) "min-legal-vector-width"="0" "no-builtins" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.module.flags = !{!0, !1, !2}
!llvm.ident = !{!3}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"PIE Level", i32 2}
!3 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!4 = !{!5, !5, i64 0}
!5 = !{!"int", !6, i64 0}
!6 = !{!"omnipotent char", !7, i64 0}
!7 = !{!"Simple C/C++ TBAA"}
