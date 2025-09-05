define i32 @foo (i32* %p, i32 %x, i1 %cond) {
entry:
  %v = load i32, i32* %p
  %sum = add i32 %v, %x
  store i32 %sum, i32* %p
  br i1 %cond, label %then, label %else
then:
  ret i32 %sum
else:
  ret i32 0
}

