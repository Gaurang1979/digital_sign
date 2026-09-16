OBJ = $(patsubst %.cpp, %.o, $(wildcard *.cpp))
include ../Rule.mak
all: $(OBJ)
	$(CXX) -w $^ -o pininfo $(SHLIBS) -ldl

$(OBJ): %.o : %.cpp
	$(CXX) -w -c $< -o $@
clean:
	rm -f pininfo  *.o
