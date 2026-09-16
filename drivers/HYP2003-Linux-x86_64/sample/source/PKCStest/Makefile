OBJ = $(patsubst %.cpp, %.o, $(wildcard *.cpp))
include ../Rule.mak

all: $(OBJ)
	$(CXX) -w -g $^ -o pkcstest $(SHLIBS) -ldl
$(OBJ): %.o : %.cpp
	$(CXX) -w -c -g $< -o $@
clean:
	rm -f pkcstest *.o
