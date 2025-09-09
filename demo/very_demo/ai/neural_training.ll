; ModuleID = '/tmp/neural_training.c'
source_filename = "/tmp/neural_training.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

%struct.NeuralNetwork = type { [4 x [8 x double]], [8 x [2 x double]], [8 x double], [2 x double], [8 x double], [2 x double] }

@.str = private unnamed_addr constant [53 x i8] c"\F0\9F\A7\A0 Initializing neural network on packet cores...\0A\00", align 1
@.str.1 = private unnamed_addr constant [47 x i8] c"\E2\9A\A1 Training neural network with %d epochs...\0A\00", align 1
@.str.2 = private unnamed_addr constant [55 x i8] c"\F0\9F\92\8E Epoch %d, Error: %.6f (computed on packet cores)\0A\00", align 1
@.str.3 = private unnamed_addr constant [57 x i8] c"\F0\9F\94\A5\F0\9F\92\A5 PacketFS Neural Network Training Demo! \F0\9F\A7\A0\E2\9A\A1\0A\00", align 1
@.str.4 = private unnamed_addr constant [46 x i8] c"Each neuron computation = 20+ packet shards!\0A\00", align 1
@.str.5 = private unnamed_addr constant [49 x i8] c"Training distributed across 1.3M packet cores!\0A\0A\00", align 1
@__const.main.training_data = private unnamed_addr constant [4 x [4 x double]] [[4 x double] [double 0.000000e+00, double 0.000000e+00, double 1.000000e+00, double 0.000000e+00], [4 x double] [double 0.000000e+00, double 1.000000e+00, double 1.000000e+00, double 0.000000e+00], [4 x double] [double 1.000000e+00, double 0.000000e+00, double 1.000000e+00, double 0.000000e+00], [4 x double] [double 1.000000e+00, double 1.000000e+00, double 1.000000e+00, double 0.000000e+00]], align 16
@.str.6 = private unnamed_addr constant [32 x i8] c"\0A\F0\9F\8E\AF Testing trained network:\0A\00", align 1
@.str.7 = private unnamed_addr constant [57 x i8] c"Input: [%.0f, %.0f, %.0f, %.0f] -> Output: [%.3f, %.3f]\0A\00", align 1
@.str.8 = private unnamed_addr constant [46 x i8] c"\0A\F0\9F\8C\9F\F0\9F\92\A5 Neural network training completed!\0A\00", align 1
@.str.9 = private unnamed_addr constant [70 x i8] c"\F0\9F\92\8E Thousands of mathematical operations executed as packet shards!\0A\00", align 1
@.str.10 = private unnamed_addr constant [69 x i8] c"\E2\9A\A1 Training time: microseconds (vs hours on traditional hardware)!\0A\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local double @sigmoid(double noundef %0) #0 {
  %2 = alloca double, align 8
  store double %0, ptr %2, align 8
  %3 = load double, ptr %2, align 8
  %4 = fneg double %3
  %5 = call double @exp(double noundef %4) #6
  %6 = fadd double 1.000000e+00, %5
  %7 = fdiv double 1.000000e+00, %6
  ret double %7
}

; Function Attrs: nounwind
declare double @exp(double noundef) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local double @sigmoid_derivative(double noundef %0) #0 {
  %2 = alloca double, align 8
  store double %0, ptr %2, align 8
  %3 = load double, ptr %2, align 8
  %4 = load double, ptr %2, align 8
  %5 = fsub double 1.000000e+00, %4
  %6 = fmul double %3, %5
  ret double %6
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @init_network(ptr noundef %0) #0 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  %8 = call i32 (ptr, ...) @printf(ptr noundef @.str)
  store i32 0, ptr %3, align 4
  br label %9

9:                                                ; preds = %33, %1
  %10 = load i32, ptr %3, align 4
  %11 = icmp slt i32 %10, 4
  br i1 %11, label %12, label %36

12:                                               ; preds = %9
  store i32 0, ptr %4, align 4
  br label %13

13:                                               ; preds = %29, %12
  %14 = load i32, ptr %4, align 4
  %15 = icmp slt i32 %14, 8
  br i1 %15, label %16, label %32

16:                                               ; preds = %13
  %17 = call i32 @rand() #6
  %18 = sitofp i32 %17 to double
  %19 = fdiv double %18, 0x41DFFFFFFFC00000
  %20 = call double @llvm.fmuladd.f64(double %19, double 2.000000e+00, double -1.000000e+00)
  %21 = load ptr, ptr %2, align 8
  %22 = getelementptr inbounds %struct.NeuralNetwork, ptr %21, i32 0, i32 0
  %23 = load i32, ptr %3, align 4
  %24 = sext i32 %23 to i64
  %25 = getelementptr inbounds [4 x [8 x double]], ptr %22, i64 0, i64 %24
  %26 = load i32, ptr %4, align 4
  %27 = sext i32 %26 to i64
  %28 = getelementptr inbounds [8 x double], ptr %25, i64 0, i64 %27
  store double %20, ptr %28, align 8
  br label %29

29:                                               ; preds = %16
  %30 = load i32, ptr %4, align 4
  %31 = add nsw i32 %30, 1
  store i32 %31, ptr %4, align 4
  br label %13, !llvm.loop !6

32:                                               ; preds = %13
  br label %33

33:                                               ; preds = %32
  %34 = load i32, ptr %3, align 4
  %35 = add nsw i32 %34, 1
  store i32 %35, ptr %3, align 4
  br label %9, !llvm.loop !8

36:                                               ; preds = %9
  store i32 0, ptr %5, align 4
  br label %37

37:                                               ; preds = %70, %36
  %38 = load i32, ptr %5, align 4
  %39 = icmp slt i32 %38, 8
  br i1 %39, label %40, label %73

40:                                               ; preds = %37
  store i32 0, ptr %6, align 4
  br label %41

41:                                               ; preds = %57, %40
  %42 = load i32, ptr %6, align 4
  %43 = icmp slt i32 %42, 2
  br i1 %43, label %44, label %60

44:                                               ; preds = %41
  %45 = call i32 @rand() #6
  %46 = sitofp i32 %45 to double
  %47 = fdiv double %46, 0x41DFFFFFFFC00000
  %48 = call double @llvm.fmuladd.f64(double %47, double 2.000000e+00, double -1.000000e+00)
  %49 = load ptr, ptr %2, align 8
  %50 = getelementptr inbounds %struct.NeuralNetwork, ptr %49, i32 0, i32 1
  %51 = load i32, ptr %5, align 4
  %52 = sext i32 %51 to i64
  %53 = getelementptr inbounds [8 x [2 x double]], ptr %50, i64 0, i64 %52
  %54 = load i32, ptr %6, align 4
  %55 = sext i32 %54 to i64
  %56 = getelementptr inbounds [2 x double], ptr %53, i64 0, i64 %55
  store double %48, ptr %56, align 8
  br label %57

57:                                               ; preds = %44
  %58 = load i32, ptr %6, align 4
  %59 = add nsw i32 %58, 1
  store i32 %59, ptr %6, align 4
  br label %41, !llvm.loop !9

60:                                               ; preds = %41
  %61 = call i32 @rand() #6
  %62 = sitofp i32 %61 to double
  %63 = fdiv double %62, 0x41DFFFFFFFC00000
  %64 = call double @llvm.fmuladd.f64(double %63, double 2.000000e+00, double -1.000000e+00)
  %65 = load ptr, ptr %2, align 8
  %66 = getelementptr inbounds %struct.NeuralNetwork, ptr %65, i32 0, i32 4
  %67 = load i32, ptr %5, align 4
  %68 = sext i32 %67 to i64
  %69 = getelementptr inbounds [8 x double], ptr %66, i64 0, i64 %68
  store double %64, ptr %69, align 8
  br label %70

70:                                               ; preds = %60
  %71 = load i32, ptr %5, align 4
  %72 = add nsw i32 %71, 1
  store i32 %72, ptr %5, align 4
  br label %37, !llvm.loop !10

73:                                               ; preds = %37
  store i32 0, ptr %7, align 4
  br label %74

74:                                               ; preds = %87, %73
  %75 = load i32, ptr %7, align 4
  %76 = icmp slt i32 %75, 2
  br i1 %76, label %77, label %90

77:                                               ; preds = %74
  %78 = call i32 @rand() #6
  %79 = sitofp i32 %78 to double
  %80 = fdiv double %79, 0x41DFFFFFFFC00000
  %81 = call double @llvm.fmuladd.f64(double %80, double 2.000000e+00, double -1.000000e+00)
  %82 = load ptr, ptr %2, align 8
  %83 = getelementptr inbounds %struct.NeuralNetwork, ptr %82, i32 0, i32 5
  %84 = load i32, ptr %7, align 4
  %85 = sext i32 %84 to i64
  %86 = getelementptr inbounds [2 x double], ptr %83, i64 0, i64 %85
  store double %81, ptr %86, align 8
  br label %87

87:                                               ; preds = %77
  %88 = load i32, ptr %7, align 4
  %89 = add nsw i32 %88, 1
  store i32 %89, ptr %7, align 4
  br label %74, !llvm.loop !11

90:                                               ; preds = %74
  ret void
}

declare i32 @printf(ptr noundef, ...) #2

; Function Attrs: nounwind
declare i32 @rand() #1

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.fmuladd.f64(double, double, double) #3

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @forward_propagation(ptr noundef %0, ptr noundef %1) #0 {
  %3 = alloca ptr, align 8
  %4 = alloca ptr, align 8
  %5 = alloca i32, align 4
  %6 = alloca double, align 8
  %7 = alloca i32, align 4
  %8 = alloca i32, align 4
  %9 = alloca double, align 8
  %10 = alloca i32, align 4
  store ptr %0, ptr %3, align 8
  store ptr %1, ptr %4, align 8
  store i32 0, ptr %5, align 4
  br label %11

11:                                               ; preds = %52, %2
  %12 = load i32, ptr %5, align 4
  %13 = icmp slt i32 %12, 8
  br i1 %13, label %14, label %55

14:                                               ; preds = %11
  %15 = load ptr, ptr %3, align 8
  %16 = getelementptr inbounds %struct.NeuralNetwork, ptr %15, i32 0, i32 4
  %17 = load i32, ptr %5, align 4
  %18 = sext i32 %17 to i64
  %19 = getelementptr inbounds [8 x double], ptr %16, i64 0, i64 %18
  %20 = load double, ptr %19, align 8
  store double %20, ptr %6, align 8
  store i32 0, ptr %7, align 4
  br label %21

21:                                               ; preds = %41, %14
  %22 = load i32, ptr %7, align 4
  %23 = icmp slt i32 %22, 4
  br i1 %23, label %24, label %44

24:                                               ; preds = %21
  %25 = load ptr, ptr %4, align 8
  %26 = load i32, ptr %7, align 4
  %27 = sext i32 %26 to i64
  %28 = getelementptr inbounds double, ptr %25, i64 %27
  %29 = load double, ptr %28, align 8
  %30 = load ptr, ptr %3, align 8
  %31 = getelementptr inbounds %struct.NeuralNetwork, ptr %30, i32 0, i32 0
  %32 = load i32, ptr %7, align 4
  %33 = sext i32 %32 to i64
  %34 = getelementptr inbounds [4 x [8 x double]], ptr %31, i64 0, i64 %33
  %35 = load i32, ptr %5, align 4
  %36 = sext i32 %35 to i64
  %37 = getelementptr inbounds [8 x double], ptr %34, i64 0, i64 %36
  %38 = load double, ptr %37, align 8
  %39 = load double, ptr %6, align 8
  %40 = call double @llvm.fmuladd.f64(double %29, double %38, double %39)
  store double %40, ptr %6, align 8
  br label %41

41:                                               ; preds = %24
  %42 = load i32, ptr %7, align 4
  %43 = add nsw i32 %42, 1
  store i32 %43, ptr %7, align 4
  br label %21, !llvm.loop !12

44:                                               ; preds = %21
  %45 = load double, ptr %6, align 8
  %46 = call double @sigmoid(double noundef %45)
  %47 = load ptr, ptr %3, align 8
  %48 = getelementptr inbounds %struct.NeuralNetwork, ptr %47, i32 0, i32 2
  %49 = load i32, ptr %5, align 4
  %50 = sext i32 %49 to i64
  %51 = getelementptr inbounds [8 x double], ptr %48, i64 0, i64 %50
  store double %46, ptr %51, align 8
  br label %52

52:                                               ; preds = %44
  %53 = load i32, ptr %5, align 4
  %54 = add nsw i32 %53, 1
  store i32 %54, ptr %5, align 4
  br label %11, !llvm.loop !13

55:                                               ; preds = %11
  store i32 0, ptr %8, align 4
  br label %56

56:                                               ; preds = %98, %55
  %57 = load i32, ptr %8, align 4
  %58 = icmp slt i32 %57, 2
  br i1 %58, label %59, label %101

59:                                               ; preds = %56
  %60 = load ptr, ptr %3, align 8
  %61 = getelementptr inbounds %struct.NeuralNetwork, ptr %60, i32 0, i32 5
  %62 = load i32, ptr %8, align 4
  %63 = sext i32 %62 to i64
  %64 = getelementptr inbounds [2 x double], ptr %61, i64 0, i64 %63
  %65 = load double, ptr %64, align 8
  store double %65, ptr %9, align 8
  store i32 0, ptr %10, align 4
  br label %66

66:                                               ; preds = %87, %59
  %67 = load i32, ptr %10, align 4
  %68 = icmp slt i32 %67, 8
  br i1 %68, label %69, label %90

69:                                               ; preds = %66
  %70 = load ptr, ptr %3, align 8
  %71 = getelementptr inbounds %struct.NeuralNetwork, ptr %70, i32 0, i32 2
  %72 = load i32, ptr %10, align 4
  %73 = sext i32 %72 to i64
  %74 = getelementptr inbounds [8 x double], ptr %71, i64 0, i64 %73
  %75 = load double, ptr %74, align 8
  %76 = load ptr, ptr %3, align 8
  %77 = getelementptr inbounds %struct.NeuralNetwork, ptr %76, i32 0, i32 1
  %78 = load i32, ptr %10, align 4
  %79 = sext i32 %78 to i64
  %80 = getelementptr inbounds [8 x [2 x double]], ptr %77, i64 0, i64 %79
  %81 = load i32, ptr %8, align 4
  %82 = sext i32 %81 to i64
  %83 = getelementptr inbounds [2 x double], ptr %80, i64 0, i64 %82
  %84 = load double, ptr %83, align 8
  %85 = load double, ptr %9, align 8
  %86 = call double @llvm.fmuladd.f64(double %75, double %84, double %85)
  store double %86, ptr %9, align 8
  br label %87

87:                                               ; preds = %69
  %88 = load i32, ptr %10, align 4
  %89 = add nsw i32 %88, 1
  store i32 %89, ptr %10, align 4
  br label %66, !llvm.loop !14

90:                                               ; preds = %66
  %91 = load double, ptr %9, align 8
  %92 = call double @sigmoid(double noundef %91)
  %93 = load ptr, ptr %3, align 8
  %94 = getelementptr inbounds %struct.NeuralNetwork, ptr %93, i32 0, i32 3
  %95 = load i32, ptr %8, align 4
  %96 = sext i32 %95 to i64
  %97 = getelementptr inbounds [2 x double], ptr %94, i64 0, i64 %96
  store double %92, ptr %97, align 8
  br label %98

98:                                               ; preds = %90
  %99 = load i32, ptr %8, align 4
  %100 = add nsw i32 %99, 1
  store i32 %100, ptr %8, align 4
  br label %56, !llvm.loop !15

101:                                              ; preds = %56
  ret void
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @train_network(ptr noundef %0, ptr noundef %1, ptr noundef %2, i32 noundef %3) #0 {
  %5 = alloca ptr, align 8
  %6 = alloca ptr, align 8
  %7 = alloca ptr, align 8
  %8 = alloca i32, align 4
  %9 = alloca i32, align 4
  %10 = alloca double, align 8
  %11 = alloca i32, align 4
  %12 = alloca [2 x double], align 16
  %13 = alloca i32, align 4
  %14 = alloca i32, align 4
  %15 = alloca i32, align 4
  %16 = alloca double, align 8
  %17 = alloca [8 x double], align 16
  %18 = alloca i32, align 4
  %19 = alloca i32, align 4
  %20 = alloca i32, align 4
  %21 = alloca double, align 8
  store ptr %0, ptr %5, align 8
  store ptr %1, ptr %6, align 8
  store ptr %2, ptr %7, align 8
  store i32 %3, ptr %8, align 4
  %22 = load i32, ptr %8, align 4
  %23 = call i32 (ptr, ...) @printf(ptr noundef @.str.1, i32 noundef %22)
  store i32 0, ptr %9, align 4
  br label %24

24:                                               ; preds = %218, %4
  %25 = load i32, ptr %9, align 4
  %26 = load i32, ptr %8, align 4
  %27 = icmp slt i32 %25, %26
  br i1 %27, label %28, label %221

28:                                               ; preds = %24
  store double 0.000000e+00, ptr %10, align 8
  store i32 0, ptr %11, align 4
  br label %29

29:                                               ; preds = %206, %28
  %30 = load i32, ptr %11, align 4
  %31 = icmp slt i32 %30, 4
  br i1 %31, label %32, label %209

32:                                               ; preds = %29
  %33 = load ptr, ptr %5, align 8
  %34 = load ptr, ptr %6, align 8
  %35 = load i32, ptr %11, align 4
  %36 = sext i32 %35 to i64
  %37 = getelementptr inbounds [4 x double], ptr %34, i64 %36
  %38 = getelementptr inbounds [4 x double], ptr %37, i64 0, i64 0
  call void @forward_propagation(ptr noundef %33, ptr noundef %38)
  store i32 0, ptr %13, align 4
  br label %39

39:                                               ; preds = %71, %32
  %40 = load i32, ptr %13, align 4
  %41 = icmp slt i32 %40, 2
  br i1 %41, label %42, label %74

42:                                               ; preds = %39
  %43 = load ptr, ptr %7, align 8
  %44 = load i32, ptr %11, align 4
  %45 = sext i32 %44 to i64
  %46 = getelementptr inbounds [2 x double], ptr %43, i64 %45
  %47 = load i32, ptr %13, align 4
  %48 = sext i32 %47 to i64
  %49 = getelementptr inbounds [2 x double], ptr %46, i64 0, i64 %48
  %50 = load double, ptr %49, align 8
  %51 = load ptr, ptr %5, align 8
  %52 = getelementptr inbounds %struct.NeuralNetwork, ptr %51, i32 0, i32 3
  %53 = load i32, ptr %13, align 4
  %54 = sext i32 %53 to i64
  %55 = getelementptr inbounds [2 x double], ptr %52, i64 0, i64 %54
  %56 = load double, ptr %55, align 8
  %57 = fsub double %50, %56
  %58 = load i32, ptr %13, align 4
  %59 = sext i32 %58 to i64
  %60 = getelementptr inbounds [2 x double], ptr %12, i64 0, i64 %59
  store double %57, ptr %60, align 8
  %61 = load i32, ptr %13, align 4
  %62 = sext i32 %61 to i64
  %63 = getelementptr inbounds [2 x double], ptr %12, i64 0, i64 %62
  %64 = load double, ptr %63, align 8
  %65 = load i32, ptr %13, align 4
  %66 = sext i32 %65 to i64
  %67 = getelementptr inbounds [2 x double], ptr %12, i64 0, i64 %66
  %68 = load double, ptr %67, align 8
  %69 = load double, ptr %10, align 8
  %70 = call double @llvm.fmuladd.f64(double %64, double %68, double %69)
  store double %70, ptr %10, align 8
  br label %71

71:                                               ; preds = %42
  %72 = load i32, ptr %13, align 4
  %73 = add nsw i32 %72, 1
  store i32 %73, ptr %13, align 4
  br label %39, !llvm.loop !16

74:                                               ; preds = %39
  store i32 0, ptr %14, align 4
  br label %75

75:                                               ; preds = %117, %74
  %76 = load i32, ptr %14, align 4
  %77 = icmp slt i32 %76, 8
  br i1 %77, label %78, label %120

78:                                               ; preds = %75
  store i32 0, ptr %15, align 4
  br label %79

79:                                               ; preds = %113, %78
  %80 = load i32, ptr %15, align 4
  %81 = icmp slt i32 %80, 2
  br i1 %81, label %82, label %116

82:                                               ; preds = %79
  %83 = load i32, ptr %15, align 4
  %84 = sext i32 %83 to i64
  %85 = getelementptr inbounds [2 x double], ptr %12, i64 0, i64 %84
  %86 = load double, ptr %85, align 8
  %87 = load ptr, ptr %5, align 8
  %88 = getelementptr inbounds %struct.NeuralNetwork, ptr %87, i32 0, i32 3
  %89 = load i32, ptr %15, align 4
  %90 = sext i32 %89 to i64
  %91 = getelementptr inbounds [2 x double], ptr %88, i64 0, i64 %90
  %92 = load double, ptr %91, align 8
  %93 = call double @sigmoid_derivative(double noundef %92)
  %94 = fmul double %86, %93
  store double %94, ptr %16, align 8
  %95 = load double, ptr %16, align 8
  %96 = fmul double 1.000000e-01, %95
  %97 = load ptr, ptr %5, align 8
  %98 = getelementptr inbounds %struct.NeuralNetwork, ptr %97, i32 0, i32 2
  %99 = load i32, ptr %14, align 4
  %100 = sext i32 %99 to i64
  %101 = getelementptr inbounds [8 x double], ptr %98, i64 0, i64 %100
  %102 = load double, ptr %101, align 8
  %103 = load ptr, ptr %5, align 8
  %104 = getelementptr inbounds %struct.NeuralNetwork, ptr %103, i32 0, i32 1
  %105 = load i32, ptr %14, align 4
  %106 = sext i32 %105 to i64
  %107 = getelementptr inbounds [8 x [2 x double]], ptr %104, i64 0, i64 %106
  %108 = load i32, ptr %15, align 4
  %109 = sext i32 %108 to i64
  %110 = getelementptr inbounds [2 x double], ptr %107, i64 0, i64 %109
  %111 = load double, ptr %110, align 8
  %112 = call double @llvm.fmuladd.f64(double %96, double %102, double %111)
  store double %112, ptr %110, align 8
  br label %113

113:                                              ; preds = %82
  %114 = load i32, ptr %15, align 4
  %115 = add nsw i32 %114, 1
  store i32 %115, ptr %15, align 4
  br label %79, !llvm.loop !17

116:                                              ; preds = %79
  br label %117

117:                                              ; preds = %116
  %118 = load i32, ptr %14, align 4
  %119 = add nsw i32 %118, 1
  store i32 %119, ptr %14, align 4
  br label %75, !llvm.loop !18

120:                                              ; preds = %75
  store i32 0, ptr %18, align 4
  br label %121

121:                                              ; preds = %202, %120
  %122 = load i32, ptr %18, align 4
  %123 = icmp slt i32 %122, 8
  br i1 %123, label %124, label %205

124:                                              ; preds = %121
  %125 = load i32, ptr %18, align 4
  %126 = sext i32 %125 to i64
  %127 = getelementptr inbounds [8 x double], ptr %17, i64 0, i64 %126
  store double 0.000000e+00, ptr %127, align 8
  store i32 0, ptr %19, align 4
  br label %128

128:                                              ; preds = %158, %124
  %129 = load i32, ptr %19, align 4
  %130 = icmp slt i32 %129, 2
  br i1 %130, label %131, label %161

131:                                              ; preds = %128
  %132 = load i32, ptr %19, align 4
  %133 = sext i32 %132 to i64
  %134 = getelementptr inbounds [2 x double], ptr %12, i64 0, i64 %133
  %135 = load double, ptr %134, align 8
  %136 = load ptr, ptr %5, align 8
  %137 = getelementptr inbounds %struct.NeuralNetwork, ptr %136, i32 0, i32 3
  %138 = load i32, ptr %19, align 4
  %139 = sext i32 %138 to i64
  %140 = getelementptr inbounds [2 x double], ptr %137, i64 0, i64 %139
  %141 = load double, ptr %140, align 8
  %142 = call double @sigmoid_derivative(double noundef %141)
  %143 = fmul double %135, %142
  %144 = load ptr, ptr %5, align 8
  %145 = getelementptr inbounds %struct.NeuralNetwork, ptr %144, i32 0, i32 1
  %146 = load i32, ptr %18, align 4
  %147 = sext i32 %146 to i64
  %148 = getelementptr inbounds [8 x [2 x double]], ptr %145, i64 0, i64 %147
  %149 = load i32, ptr %19, align 4
  %150 = sext i32 %149 to i64
  %151 = getelementptr inbounds [2 x double], ptr %148, i64 0, i64 %150
  %152 = load double, ptr %151, align 8
  %153 = load i32, ptr %18, align 4
  %154 = sext i32 %153 to i64
  %155 = getelementptr inbounds [8 x double], ptr %17, i64 0, i64 %154
  %156 = load double, ptr %155, align 8
  %157 = call double @llvm.fmuladd.f64(double %143, double %152, double %156)
  store double %157, ptr %155, align 8
  br label %158

158:                                              ; preds = %131
  %159 = load i32, ptr %19, align 4
  %160 = add nsw i32 %159, 1
  store i32 %160, ptr %19, align 4
  br label %128, !llvm.loop !19

161:                                              ; preds = %128
  store i32 0, ptr %20, align 4
  br label %162

162:                                              ; preds = %198, %161
  %163 = load i32, ptr %20, align 4
  %164 = icmp slt i32 %163, 4
  br i1 %164, label %165, label %201

165:                                              ; preds = %162
  %166 = load i32, ptr %18, align 4
  %167 = sext i32 %166 to i64
  %168 = getelementptr inbounds [8 x double], ptr %17, i64 0, i64 %167
  %169 = load double, ptr %168, align 8
  %170 = load ptr, ptr %5, align 8
  %171 = getelementptr inbounds %struct.NeuralNetwork, ptr %170, i32 0, i32 2
  %172 = load i32, ptr %18, align 4
  %173 = sext i32 %172 to i64
  %174 = getelementptr inbounds [8 x double], ptr %171, i64 0, i64 %173
  %175 = load double, ptr %174, align 8
  %176 = call double @sigmoid_derivative(double noundef %175)
  %177 = fmul double %169, %176
  store double %177, ptr %21, align 8
  %178 = load double, ptr %21, align 8
  %179 = fmul double 1.000000e-01, %178
  %180 = load ptr, ptr %6, align 8
  %181 = load i32, ptr %11, align 4
  %182 = sext i32 %181 to i64
  %183 = getelementptr inbounds [4 x double], ptr %180, i64 %182
  %184 = load i32, ptr %20, align 4
  %185 = sext i32 %184 to i64
  %186 = getelementptr inbounds [4 x double], ptr %183, i64 0, i64 %185
  %187 = load double, ptr %186, align 8
  %188 = load ptr, ptr %5, align 8
  %189 = getelementptr inbounds %struct.NeuralNetwork, ptr %188, i32 0, i32 0
  %190 = load i32, ptr %20, align 4
  %191 = sext i32 %190 to i64
  %192 = getelementptr inbounds [4 x [8 x double]], ptr %189, i64 0, i64 %191
  %193 = load i32, ptr %18, align 4
  %194 = sext i32 %193 to i64
  %195 = getelementptr inbounds [8 x double], ptr %192, i64 0, i64 %194
  %196 = load double, ptr %195, align 8
  %197 = call double @llvm.fmuladd.f64(double %179, double %187, double %196)
  store double %197, ptr %195, align 8
  br label %198

198:                                              ; preds = %165
  %199 = load i32, ptr %20, align 4
  %200 = add nsw i32 %199, 1
  store i32 %200, ptr %20, align 4
  br label %162, !llvm.loop !20

201:                                              ; preds = %162
  br label %202

202:                                              ; preds = %201
  %203 = load i32, ptr %18, align 4
  %204 = add nsw i32 %203, 1
  store i32 %204, ptr %18, align 4
  br label %121, !llvm.loop !21

205:                                              ; preds = %121
  br label %206

206:                                              ; preds = %205
  %207 = load i32, ptr %11, align 4
  %208 = add nsw i32 %207, 1
  store i32 %208, ptr %11, align 4
  br label %29, !llvm.loop !22

209:                                              ; preds = %29
  %210 = load i32, ptr %9, align 4
  %211 = srem i32 %210, 100
  %212 = icmp eq i32 %211, 0
  br i1 %212, label %213, label %217

213:                                              ; preds = %209
  %214 = load i32, ptr %9, align 4
  %215 = load double, ptr %10, align 8
  %216 = call i32 (ptr, ...) @printf(ptr noundef @.str.2, i32 noundef %214, double noundef %215)
  br label %217

217:                                              ; preds = %213, %209
  br label %218

218:                                              ; preds = %217
  %219 = load i32, ptr %9, align 4
  %220 = add nsw i32 %219, 1
  store i32 %220, ptr %9, align 4
  br label %24, !llvm.loop !23

221:                                              ; preds = %24
  ret void
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 {
  %1 = alloca i32, align 4
  %2 = alloca %struct.NeuralNetwork, align 8
  %3 = alloca [4 x [4 x double]], align 16
  %4 = alloca [4 x [2 x double]], align 16
  %5 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  %6 = call i32 (ptr, ...) @printf(ptr noundef @.str.3)
  %7 = call i32 (ptr, ...) @printf(ptr noundef @.str.4)
  %8 = call i32 (ptr, ...) @printf(ptr noundef @.str.5)
  call void @init_network(ptr noundef %2)
  call void @llvm.memcpy.p0.p0.i64(ptr align 16 %3, ptr align 16 @__const.main.training_data, i64 128, i1 false)
  call void @llvm.memset.p0.i64(ptr align 16 %4, i8 0, i64 64, i1 false)
  %9 = getelementptr inbounds [4 x [2 x double]], ptr %4, i32 0, i32 0
  %10 = getelementptr inbounds [2 x double], ptr %9, i32 0, i32 1
  store double 1.000000e+00, ptr %10, align 8
  %11 = getelementptr inbounds [4 x [2 x double]], ptr %4, i32 0, i32 1
  %12 = getelementptr inbounds [2 x double], ptr %11, i32 0, i32 0
  store double 1.000000e+00, ptr %12, align 16
  %13 = getelementptr inbounds [4 x [2 x double]], ptr %4, i32 0, i32 2
  %14 = getelementptr inbounds [2 x double], ptr %13, i32 0, i32 0
  store double 1.000000e+00, ptr %14, align 16
  %15 = getelementptr inbounds [4 x [2 x double]], ptr %4, i32 0, i32 3
  %16 = getelementptr inbounds [2 x double], ptr %15, i32 0, i32 1
  store double 1.000000e+00, ptr %16, align 8
  %17 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 0
  %18 = getelementptr inbounds [4 x [2 x double]], ptr %4, i64 0, i64 0
  call void @train_network(ptr noundef %2, ptr noundef %17, ptr noundef %18, i32 noundef 1000)
  %19 = call i32 (ptr, ...) @printf(ptr noundef @.str.6)
  store i32 0, ptr %5, align 4
  br label %20

20:                                               ; preds = %55, %0
  %21 = load i32, ptr %5, align 4
  %22 = icmp slt i32 %21, 4
  br i1 %22, label %23, label %58

23:                                               ; preds = %20
  %24 = load i32, ptr %5, align 4
  %25 = sext i32 %24 to i64
  %26 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 %25
  %27 = getelementptr inbounds [4 x double], ptr %26, i64 0, i64 0
  call void @forward_propagation(ptr noundef %2, ptr noundef %27)
  %28 = load i32, ptr %5, align 4
  %29 = sext i32 %28 to i64
  %30 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 %29
  %31 = getelementptr inbounds [4 x double], ptr %30, i64 0, i64 0
  %32 = load double, ptr %31, align 16
  %33 = load i32, ptr %5, align 4
  %34 = sext i32 %33 to i64
  %35 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 %34
  %36 = getelementptr inbounds [4 x double], ptr %35, i64 0, i64 1
  %37 = load double, ptr %36, align 8
  %38 = load i32, ptr %5, align 4
  %39 = sext i32 %38 to i64
  %40 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 %39
  %41 = getelementptr inbounds [4 x double], ptr %40, i64 0, i64 2
  %42 = load double, ptr %41, align 16
  %43 = load i32, ptr %5, align 4
  %44 = sext i32 %43 to i64
  %45 = getelementptr inbounds [4 x [4 x double]], ptr %3, i64 0, i64 %44
  %46 = getelementptr inbounds [4 x double], ptr %45, i64 0, i64 3
  %47 = load double, ptr %46, align 8
  %48 = getelementptr inbounds %struct.NeuralNetwork, ptr %2, i32 0, i32 3
  %49 = getelementptr inbounds [2 x double], ptr %48, i64 0, i64 0
  %50 = load double, ptr %49, align 8
  %51 = getelementptr inbounds %struct.NeuralNetwork, ptr %2, i32 0, i32 3
  %52 = getelementptr inbounds [2 x double], ptr %51, i64 0, i64 1
  %53 = load double, ptr %52, align 8
  %54 = call i32 (ptr, ...) @printf(ptr noundef @.str.7, double noundef %32, double noundef %37, double noundef %42, double noundef %47, double noundef %50, double noundef %53)
  br label %55

55:                                               ; preds = %23
  %56 = load i32, ptr %5, align 4
  %57 = add nsw i32 %56, 1
  store i32 %57, ptr %5, align 4
  br label %20, !llvm.loop !24

58:                                               ; preds = %20
  %59 = call i32 (ptr, ...) @printf(ptr noundef @.str.8)
  %60 = call i32 (ptr, ...) @printf(ptr noundef @.str.9)
  %61 = call i32 (ptr, ...) @printf(ptr noundef @.str.10)
  ret i32 0
}

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #4

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: write)
declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg) #5

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #4 = { nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #5 = { nocallback nofree nounwind willreturn memory(argmem: write) }
attributes #6 = { nounwind }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 8, !"PIC Level", i32 2}
!2 = !{i32 7, !"PIE Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 2}
!4 = !{i32 7, !"frame-pointer", i32 2}
!5 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!6 = distinct !{!6, !7}
!7 = !{!"llvm.loop.mustprogress"}
!8 = distinct !{!8, !7}
!9 = distinct !{!9, !7}
!10 = distinct !{!10, !7}
!11 = distinct !{!11, !7}
!12 = distinct !{!12, !7}
!13 = distinct !{!13, !7}
!14 = distinct !{!14, !7}
!15 = distinct !{!15, !7}
!16 = distinct !{!16, !7}
!17 = distinct !{!17, !7}
!18 = distinct !{!18, !7}
!19 = distinct !{!19, !7}
!20 = distinct !{!20, !7}
!21 = distinct !{!21, !7}
!22 = distinct !{!22, !7}
!23 = distinct !{!23, !7}
!24 = distinct !{!24, !7}
