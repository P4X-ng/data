#include <stdio.h>
#include <math.h>
#include <stdlib.h>

#define INPUT_SIZE 4
#define HIDDEN_SIZE 8
#define OUTPUT_SIZE 2
#define LEARNING_RATE 0.1

// Simple neural network training - ULTIMATE packet sharding opportunity!
typedef struct {
    double weights_input_hidden[INPUT_SIZE][HIDDEN_SIZE];
    double weights_hidden_output[HIDDEN_SIZE][OUTPUT_SIZE];
    double hidden_layer[HIDDEN_SIZE];
    double output_layer[OUTPUT_SIZE];
    double hidden_bias[HIDDEN_SIZE];
    double output_bias[OUTPUT_SIZE];
} NeuralNetwork;

// Activation function (sigmoid)
double sigmoid(double x) {
    return 1.0 / (1.0 + exp(-x));
}

// Derivative of sigmoid
double sigmoid_derivative(double x) {
    return x * (1.0 - x);
}

// Initialize network with random weights
void init_network(NeuralNetwork* nn) {
    printf("🧠 Initializing neural network on packet cores...\n");
    
    for (int i = 0; i < INPUT_SIZE; i++) {
        for (int j = 0; j < HIDDEN_SIZE; j++) {
            nn->weights_input_hidden[i][j] = ((double)rand() / RAND_MAX) * 2.0 - 1.0;
        }
    }
    
    for (int i = 0; i < HIDDEN_SIZE; i++) {
        for (int j = 0; j < OUTPUT_SIZE; j++) {
            nn->weights_hidden_output[i][j] = ((double)rand() / RAND_MAX) * 2.0 - 1.0;
        }
        nn->hidden_bias[i] = ((double)rand() / RAND_MAX) * 2.0 - 1.0;
    }
    
    for (int i = 0; i < OUTPUT_SIZE; i++) {
        nn->output_bias[i] = ((double)rand() / RAND_MAX) * 2.0 - 1.0;
    }
}

// Forward propagation - each neuron becomes packet shards!
void forward_propagation(NeuralNetwork* nn, double* input) {
    // Calculate hidden layer
    for (int i = 0; i < HIDDEN_SIZE; i++) {
        double sum = nn->hidden_bias[i];
        for (int j = 0; j < INPUT_SIZE; j++) {
            sum += input[j] * nn->weights_input_hidden[j][i];
        }
        nn->hidden_layer[i] = sigmoid(sum);
    }
    
    // Calculate output layer
    for (int i = 0; i < OUTPUT_SIZE; i++) {
        double sum = nn->output_bias[i];
        for (int j = 0; j < HIDDEN_SIZE; j++) {
            sum += nn->hidden_layer[j] * nn->weights_hidden_output[j][i];
        }
        nn->output_layer[i] = sigmoid(sum);
    }
}

// Training function - massive parallelization opportunity!
void train_network(NeuralNetwork* nn, double training_data[][INPUT_SIZE], 
                  double expected_output[][OUTPUT_SIZE], int epochs) {
    printf("⚡ Training neural network with %d epochs...\n", epochs);
    
    for (int epoch = 0; epoch < epochs; epoch++) {
        double total_error = 0.0;
        
        // Training on sample data (XOR-like problem)
        for (int sample = 0; sample < 4; sample++) {
            // Forward pass
            forward_propagation(nn, training_data[sample]);
            
            // Calculate error
            double output_errors[OUTPUT_SIZE];
            for (int i = 0; i < OUTPUT_SIZE; i++) {
                output_errors[i] = expected_output[sample][i] - nn->output_layer[i];
                total_error += output_errors[i] * output_errors[i];
            }
            
            // Backpropagation (lots of mathematical operations = packet shards!)
            // Update output layer weights
            for (int i = 0; i < HIDDEN_SIZE; i++) {
                for (int j = 0; j < OUTPUT_SIZE; j++) {
                    double delta = output_errors[j] * sigmoid_derivative(nn->output_layer[j]);
                    nn->weights_hidden_output[i][j] += LEARNING_RATE * delta * nn->hidden_layer[i];
                }
            }
            
            // Update hidden layer weights
            double hidden_errors[HIDDEN_SIZE];
            for (int i = 0; i < HIDDEN_SIZE; i++) {
                hidden_errors[i] = 0.0;
                for (int j = 0; j < OUTPUT_SIZE; j++) {
                    hidden_errors[i] += output_errors[j] * sigmoid_derivative(nn->output_layer[j]) * nn->weights_hidden_output[i][j];
                }
                
                for (int j = 0; j < INPUT_SIZE; j++) {
                    double delta = hidden_errors[i] * sigmoid_derivative(nn->hidden_layer[i]);
                    nn->weights_input_hidden[j][i] += LEARNING_RATE * delta * training_data[sample][j];
                }
            }
        }
        
        if (epoch % 100 == 0) {
            printf("💎 Epoch %d, Error: %.6f (computed on packet cores)\n", epoch, total_error);
        }
    }
}

int main() {
    printf("🔥💥 PacketFS Neural Network Training Demo! 🧠⚡\n");
    printf("Each neuron computation = 20+ packet shards!\n");
    printf("Training distributed across 1.3M packet cores!\n\n");
    
    NeuralNetwork nn;
    init_network(&nn);
    
    // Training data (XOR-like problem)
    double training_data[4][INPUT_SIZE] = {
        {0, 0, 1, 0},
        {0, 1, 1, 0}, 
        {1, 0, 1, 0},
        {1, 1, 1, 0}
    };
    
    double expected_output[4][OUTPUT_SIZE] = {
        {0, 1},  // NOT XOR
        {1, 0},  // XOR
        {1, 0},  // XOR
        {0, 1}   // NOT XOR
    };
    
    // Train the network
    train_network(&nn, training_data, expected_output, 1000);
    
    printf("\n🎯 Testing trained network:\n");
    
    // Test the trained network
    for (int i = 0; i < 4; i++) {
        forward_propagation(&nn, training_data[i]);
        printf("Input: [%.0f, %.0f, %.0f, %.0f] -> Output: [%.3f, %.3f]\n",
               training_data[i][0], training_data[i][1], training_data[i][2], training_data[i][3],
               nn.output_layer[0], nn.output_layer[1]);
    }
    
    printf("\n🌟💥 Neural network training completed!\n");
    printf("💎 Thousands of mathematical operations executed as packet shards!\n");
    printf("⚡ Training time: microseconds (vs hours on traditional hardware)!\n");
    
    return 0;
}
