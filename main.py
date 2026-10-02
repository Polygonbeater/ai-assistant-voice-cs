from llama_core import LlamaModuleManager
from blender_receiver import handle_auto_rig
from llama_module import AutoRigAndSkinModule

manager = LlamaModuleManager()
manager.register_module(AutoRigAndSkinModule)

def main():
    # Simulate receiving 'auto_rig' command
    handle_auto_rig()

if __name__ == '__main__':
    main()
